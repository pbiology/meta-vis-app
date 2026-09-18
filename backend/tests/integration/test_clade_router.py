# tests/integration/test_clade_router.py

from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.routers.samples import router
from tests.helpers import insert_case as seed_case
from tests.helpers import make_test_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ABOVE_FAMILY = [131567, 2, 3379134, 1224, 1236, 91347]

# (taxon_id, name, rank, ancestors below family)
TAXA = [
    (543, "Enterobacteriaceae", "family", []),
    (561, "Escherichia", "genus", [543]),
    (562, "Escherichia coli", "species", [543, 561]),
    (83333, "Escherichia coli K-12", "strain", [543, 561, 562]),
    (83334, "Escherichia coli O157:H7", "serotype", [543, 561, 562]),
    (620, "Shigella", "genus", [543]),
]


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


async def seed_taxa(db, *, with_lineage: bool = True):
    for taxon_id, name, rank, below_family in TAXA:
        doc = {
            "taxon_id": taxon_id,
            "name": name,
            "rank": rank,
            "taxdump_version": "2026-09-17",
        }
        if with_lineage:
            doc["ancestor_ids"] = [*ABOVE_FAMILY, *below_family]
        await db["taxa"].insert_one(doc)


async def insert_sample(
    db,
    analysis_id,
    sample_id,
    *,
    sample_type="sample",
    nucleic_acid="DNA",
    kraken2=None,
    extra=None,
):
    profiles = (
        [{"classifier": "kraken2", "classifier_db": "db", "profile": kraken2}]
        if kraken2 is not None
        else []
    )
    result = await db["samples"].insert_one(
        {
            "analysis_id": analysis_id,
            "is_latest_analysis": True,
            "case_id": "testcase",
            "sample_id": sample_id,
            "sample_type": sample_type,
            "nucleic_acid": nucleic_acid,
            "profiles": profiles,
            "ingested_at": datetime.now(timezone.utc),
            **(extra or {}),
        }
    )
    return result.inserted_id


def entry(taxon_id, abundance, name="x"):
    return {"taxon_id": taxon_id, "name": name, "abundance": abundance}


def find(node, taxon_id):
    if node["taxon_id"] == taxon_id:
        return node
    for c in node["children"]:
        found = find(c, taxon_id)
        if found:
            return found
    return None


def get_clade(client, oid, taxon_id, classifier="kraken2"):
    return client.get(
        f"/api/v1/samples/{oid}/clade",
        params={"classifier": classifier, "taxon_id": taxon_id},
    )


# ---------------------------------------------------------------------------
# GET /samples/{sample_id}/clade
# ---------------------------------------------------------------------------


class TestGetClade:
    async def test_clicking_strain_opens_tree_at_genus(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db, analysis_id, "S1", kraken2=[entry(0, 900), entry(83334, 100)]
        )

        resp = get_clade(client, oid, 83334)

        assert resp.status_code == 200
        body = resp.json()
        assert body["clicked"]["taxon_id"] == 83334
        assert body["anchor"]["taxon_id"] == 561
        assert body["root"]["taxon_id"] == 561
        # E. coli has no reads of its own but connects the serotype to the genus.
        e_coli = find(body["root"], 562)
        assert e_coli["is_connector"]
        assert find(body["root"], 83334)["cells"]["S1"]["direct_rpm"] == 100_000.0

    async def test_includes_taxa_only_in_negative_control(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db, analysis_id, "S1", kraken2=[entry(83334, 100)]
        )
        await insert_sample(
            fake_db,
            analysis_id,
            "NTC1",
            sample_type="negative_ctrl",
            kraken2=[entry(83333, 7)],
        )

        body = get_clade(client, oid, 83334).json()

        assert [c["sample_id"] for c in body["columns"]] == ["S1", "NTC1"]
        k12 = find(body["root"], 83333)
        assert k12["cells"]["S1"]["direct"] == 0
        assert k12["cells"]["NTC1"]["direct"] == 7

    async def test_excludes_taxa_outside_the_anchor(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db, analysis_id, "S1", kraken2=[entry(562, 10), entry(620, 50)]
        )

        body = get_clade(client, oid, 562).json()

        assert find(body["root"], 620) is None
        assert body["unplaced"] == []

    async def test_compares_only_matching_negative_controls(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        other_analysis = await seed_case(fake_db, "othercase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(562, 1)])
        await insert_sample(
            fake_db,
            analysis_id,
            "NTC_DNA",
            sample_type="negative_ctrl",
            kraken2=[entry(562, 1)],
        )
        await insert_sample(
            fake_db,
            analysis_id,
            "NTC_RNA",
            sample_type="negative_ctrl",
            nucleic_acid="RNA",
            kraken2=[entry(562, 1)],
        )
        await insert_sample(
            fake_db,
            analysis_id,
            "POS",
            sample_type="positive_ctrl",
            kraken2=[entry(562, 1)],
        )
        await insert_sample(
            fake_db,
            other_analysis,
            "NTC_OTHER_RUN",
            sample_type="negative_ctrl",
            kraken2=[entry(562, 1)],
        )

        body = get_clade(client, oid, 562).json()

        assert [c["sample_id"] for c in body["columns"]] == ["S1", "NTC_DNA"]

    async def test_negative_control_is_not_compared_with_itself(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        ntc = await insert_sample(
            fake_db,
            analysis_id,
            "NTC1",
            sample_type="negative_ctrl",
            kraken2=[entry(562, 1)],
        )

        body = get_clade(client, ntc, 562).json()

        assert [c["sample_id"] for c in body["columns"]] == ["NTC1"]

    async def test_control_without_classifier_profile_has_no_cells(
        self, client, fake_db
    ):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(562, 1)])
        await insert_sample(fake_db, analysis_id, "NTC1", sample_type="negative_ctrl")

        body = get_clade(client, oid, 562).json()

        ntc_column = body["columns"][1]
        assert ntc_column["has_profile"] is False
        assert ntc_column["classifier_total"] is None
        assert "NTC1" not in body["root"]["cells"]

    async def test_merged_id_signal_lands_on_current_taxon(self, client, fake_db):
        await seed_taxa(fake_db)
        await fake_db["taxa_retired"].insert_one(
            {"taxon_id": 12, "status": "merged", "merged_into": 562}
        )
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db, analysis_id, "S1", kraken2=[entry(12, 4), entry(562, 10)]
        )

        body = get_clade(client, oid, 562).json()

        e_coli = find(body["root"], 562)
        assert e_coli["cells"]["S1"]["direct"] == 14
        assert e_coli["merged_from"] == [12]

    async def test_clicking_merged_id_resolves_to_current_taxon(self, client, fake_db):
        await seed_taxa(fake_db)
        await fake_db["taxa_retired"].insert_one(
            {"taxon_id": 12, "status": "merged", "merged_into": 562}
        )
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(12, 4)])

        body = get_clade(client, oid, 12).json()

        assert body["clicked"]["taxon_id"] == 562

    async def test_reports_deleted_and_unknown_ids_as_unplaced(self, client, fake_db):
        await seed_taxa(fake_db)
        await fake_db["taxa_retired"].insert_one(
            {"taxon_id": 99, "status": "deleted", "merged_into": None}
        )
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db,
            analysis_id,
            "S1",
            kraken2=[entry(562, 1), entry(99, 2, "gone"), entry(777, 3, "unknown")],
        )

        body = get_clade(client, oid, 562).json()

        assert [(u["taxon_id"], u["reason"]) for u in body["unplaced"]] == [
            (99, "deleted"),
            (777, "not_in_taxonomy"),
        ]

    async def test_trana_sample_uses_fraction_without_rpm(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(
            fake_db,
            analysis_id,
            "S1",
            kraken2=[entry(562, 0.25)],
            extra={"trana": {"nanoplot_unprocessed": {"number_of_reads": 10}}},
        )

        body = get_clade(client, oid, 562).json()

        assert body["unit"] == "fraction"
        assert body["columns"][0]["classifier_total"] is None
        assert find(body["root"], 562)["cells"]["S1"]["direct_rpm"] is None

    async def test_taxonomy_without_lineage_returns_409(self, client, fake_db):
        await seed_taxa(fake_db, with_lineage=False)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(562, 1)])

        resp = get_clade(client, oid, 562)

        assert resp.status_code == 409
        assert "load_taxonomy.py" in resp.json()["detail"]

    async def test_ingest_placeholder_taxon_returns_404_not_409(self, client, fake_db):
        # Ingest writes this shape for profile IDs the reference lacks.
        await seed_taxa(fake_db)
        await fake_db["taxa"].insert_one(
            {"taxon_id": 0, "name": "0", "rank": None, "taxdump_version": None}
        )
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(0, 5)])

        resp = get_clade(client, oid, 0)

        assert resp.status_code == 404
        assert "not in the loaded taxonomy" in resp.json()["detail"]

    async def test_clicking_deleted_taxon_returns_404(self, client, fake_db):
        await seed_taxa(fake_db)
        await fake_db["taxa_retired"].insert_one(
            {"taxon_id": 99, "status": "deleted", "merged_into": None}
        )
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(99, 1)])

        resp = get_clade(client, oid, 99)

        assert resp.status_code == 404
        assert "deleted" in resp.json()["detail"]

    async def test_unknown_classifier_returns_404(self, client, fake_db):
        await seed_taxa(fake_db)
        analysis_id = await seed_case(fake_db, "testcase")
        oid = await insert_sample(fake_db, analysis_id, "S1", kraken2=[entry(562, 1)])

        resp = get_clade(client, oid, 562, classifier="centrifuge")

        assert resp.status_code == 404

    async def test_unknown_sample_returns_404(self, client, fake_db):
        resp = get_clade(client, ObjectId(), 562)

        assert resp.status_code == 404

    def test_malformed_sample_id_returns_422(self, client):
        resp = get_clade(client, "not-an-object-id", 562)

        assert resp.status_code == 422

    def test_missing_taxon_id_returns_422(self, client):
        resp = client.get(
            f"/api/v1/samples/{ObjectId()}/clade", params={"classifier": "kraken2"}
        )

        assert resp.status_code == 422
