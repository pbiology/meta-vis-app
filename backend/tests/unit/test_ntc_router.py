# tests/unit/test_ntc_router.py
#
# Tests for the NTC trends router.
# Uses mongomock_motor for an in-memory MongoDB — the same pattern as the
# integration tests — because the router performs real query + aggregation
# logic that is worth testing end-to-end without a live database.
#
# asyncio_mode = "auto" is set in pyproject.toml, so all async test methods
# are picked up automatically by pytest-asyncio without any extra decoration.

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from mongomock_motor import AsyncMongoMockClient

from app.routers.ntc import router as ntc_router, invalidate_ntc_trends_cache
from app.database import get_db
from app.auth.utils import get_current_user


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_trends_cache():
    invalidate_ntc_trends_cache()


@pytest.fixture
def fake_db():
    client = AsyncMongoMockClient()
    return client["test_db"]


def make_app(fake_db):
    app = FastAPI()
    app.include_router(ntc_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "testuser",
        "role": "reader",
    }
    return app


def make_ntc_doc(
    sample_id: str,
    case_id_str: str,
    material: str,
    order_date: str,
    profile: list[dict] | None = None,
    classified_reads: int | None = None,
) -> dict:
    """Build a minimal sample document as stored in MongoDB."""
    doc: dict = {
        "sample_id": sample_id,
        "case_id_str": case_id_str,
        "sample_type": "negative_ctrl",
        "material": material,
        "order_date": order_date,
        "profiles": [],
        "taxprofiler": {},
    }
    if profile is not None:
        doc["profiles"] = [{"classifier": "kraken2", "profile": profile}]
    if classified_reads is not None:
        doc["taxprofiler"] = {
            "classifiers": {"kraken2": {"classified_reads": classified_reads}}
        }
    return doc


def make_taxon(
    taxon_id: int,
    name: str,
    abundance: float,
    superkingdom: str = "Bacteria",
    rank: str = "species",
) -> dict:
    return {
        "taxon_id": taxon_id,
        "name": name,
        "abundance": abundance,
        "superkingdom": superkingdom,
        "rank": rank,
    }


# ---------------------------------------------------------------------------
# No data cases
# ---------------------------------------------------------------------------


class TestNtcTrendsEmpty:
    async def test_no_ntcs_returns_empty_response(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ntcs"] == 0
        assert data["read_counts"] == []
        assert data["recurring_taxa"] == []

    async def test_no_ntcs_response_contains_material_and_window(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=RNA&window_days=30")
        data = resp.json()
        assert data["material"] == "RNA"
        assert data["window_days"] == 30

    async def test_dna_ntcs_not_returned_for_rna_query(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01")
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=RNA")
        assert resp.json()["total_ntcs"] == 0

    async def test_non_ntc_samples_excluded(self, fake_db):
        doc = make_ntc_doc("S-1", "case-1", "DNA", "2026-04-01")
        doc["sample_type"] = "sample"
        await fake_db["samples"].insert_one(doc)
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        assert resp.json()["total_ntcs"] == 0


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestNtcTrendsValidation:
    async def test_missing_material_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends")
        assert resp.status_code == 422

    async def test_invalid_material_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=INVALID")
        assert resp.status_code == 422

    async def test_window_days_below_minimum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&window_days=6")
        assert resp.status_code == 422

    async def test_window_days_above_maximum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&window_days=366")
        assert resp.status_code == 422

    async def test_min_reads_below_minimum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&min_reads=0")
        assert resp.status_code == 422

    async def test_min_case_pct_above_maximum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&min_case_pct=1.1")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Read counts
# ---------------------------------------------------------------------------


class TestNtcReadCounts:
    async def test_classified_reads_from_multiqc_qc_field(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", classified_reads=500)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        counts = resp.json()["read_counts"]
        assert len(counts) == 1
        assert counts[0]["classified_reads"] == 500
        assert counts[0]["sample_id"] == "NTC-1"
        assert counts[0]["case_id"] == "case-1"

    async def test_classified_reads_fallback_to_root_node_in_profile(self, fake_db):
        profile = [
            make_taxon(1, "root", 300),
            make_taxon(1743, "Cutibacterium acnes", 25),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["classified_reads"] == 300

    async def test_classified_reads_null_when_no_qc_and_no_profile(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01")
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["classified_reads"] is None

    async def test_read_counts_sorted_by_order_date(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-B", "case-B", "DNA", "2026-04-10", classified_reads=200)
        )
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-A", "case-A", "DNA", "2026-04-01", classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["sample_id"] == "NTC-A"
        assert counts[1]["sample_id"] == "NTC-B"

    async def test_ntc_outside_window_excluded_from_read_counts(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc(
                "NTC-OLD", "case-old", "DNA", "2020-01-01", classified_reads=999
            )
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&window_days=90")
        assert resp.json()["total_ntcs"] == 0


# ---------------------------------------------------------------------------
# Recurring taxa — filtering logic
# ---------------------------------------------------------------------------


class TestRecurringTaxa:
    async def test_taxon_above_min_reads_in_multiple_cases_is_recurring(self, fake_db):
        contaminant = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1", "case-1", "DNA", "2026-04-01", profile=[contaminant]
                ),
                make_ntc_doc(
                    "NTC-2", "case-2", "DNA", "2026-04-02", profile=[contaminant]
                ),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert len(taxa) == 1
        assert taxa[0]["taxon_id"] == 1743
        assert taxa[0]["taxon_name"] == "Cutibacterium acnes"
        assert taxa[0]["case_count"] == 2

    async def test_taxon_at_or_below_min_reads_excluded(self, fake_db):
        # abundance=3, min_reads=3 — must be strictly greater than
        low = make_taxon(1743, "Cutibacterium acnes", 3)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[low]),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02", profile=[low]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []

    async def test_taxon_above_min_reads_threshold(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 4)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        assert len(resp.json()["recurring_taxa"]) == 1

    async def test_host_taxon_ids_excluded_from_recurring_taxa(self, fake_db):
        host = make_taxon(9606, "Homo sapiens", 100, superkingdom="Eukaryota")
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[host]),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02", profile=[host]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=1&min_case_pct=0.1"
        )
        taxon_ids = [t["taxon_id"] for t in resp.json()["recurring_taxa"]]
        assert 9606 not in taxon_ids

    async def test_all_host_taxon_ids_excluded(self, fake_db):
        from app.constants import HOST_TAXON_IDS

        host_entries = [make_taxon(tid, f"host-{tid}", 100) for tid in HOST_TAXON_IDS]
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1", "case-1", "DNA", "2026-04-01", profile=host_entries
                ),
                make_ntc_doc(
                    "NTC-2", "case-2", "DNA", "2026-04-02", profile=host_entries
                ),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=1&min_case_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []

    async def test_taxon_in_single_case_excluded_when_min_case_pct_requires_more(
        self, fake_db
    ):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        # 10 NTCs, taxon in only 1 case; min_case_count = max(1, round(10*0.5)) = 5
        docs = [
            make_ntc_doc(f"NTC-{i}", f"case-{i}", "DNA", "2026-04-01") for i in range(9)
        ] + [make_ntc_doc("NTC-9", "case-9", "DNA", "2026-04-01", profile=[taxon])]
        await fake_db["samples"].insert_many(docs)
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.5"
        )
        assert resp.json()["recurring_taxa"] == []

    async def test_taxon_counted_once_per_case_when_seen_in_multiple_profiles(
        self, fake_db
    ):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        profile_with_duplicate = [taxon, taxon]
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1",
                    "case-1",
                    "DNA",
                    "2026-04-01",
                    profile=profile_with_duplicate,
                ),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert len(taxa) == 1
        assert taxa[0]["case_count"] == 2

    async def test_recurring_taxa_sorted_by_case_count_descending(self, fake_db):
        taxon_a = make_taxon(1743, "Taxon-A", 10)
        taxon_b = make_taxon(329, "Taxon-B", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1", "case-1", "DNA", "2026-04-01", profile=[taxon_a, taxon_b]
                ),
                make_ntc_doc(
                    "NTC-2", "case-2", "DNA", "2026-04-02", profile=[taxon_a, taxon_b]
                ),
                make_ntc_doc("NTC-3", "case-3", "DNA", "2026-04-03", profile=[taxon_b]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert taxa[0]["taxon_id"] == 329  # Taxon-B — 3 cases
        assert taxa[1]["taxon_id"] == 1743  # Taxon-A — 2 cases

    async def test_occurrences_sorted_by_order_date(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-B", "case-B", "DNA", "2026-04-10", profile=[taxon]),
                make_ntc_doc("NTC-A", "case-A", "DNA", "2026-04-01", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        occ = resp.json()["recurring_taxa"][0]["occurrences"]
        assert occ[0]["order_date"] == "2026-04-01"
        assert occ[1]["order_date"] == "2026-04-10"

    async def test_non_kraken2_profiles_ignored(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        docs = [
            {
                "sample_id": "NTC-1",
                "case_id_str": "case-1",
                "sample_type": "negative_ctrl",
                "material": "DNA",
                "order_date": "2026-04-01",
                "profiles": [{"classifier": "centrifuge", "profile": [taxon]}],
                "taxprofiler": {},
            },
            {
                "sample_id": "NTC-2",
                "case_id_str": "case-2",
                "sample_type": "negative_ctrl",
                "material": "DNA",
                "order_date": "2026-04-02",
                "profiles": [{"classifier": "centrifuge", "profile": [taxon]}],
                "taxprofiler": {},
            },
        ]
        await fake_db["samples"].insert_many(docs)
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []


# ---------------------------------------------------------------------------
# Kingdom breakdown
# ---------------------------------------------------------------------------


class TestKingdomBreakdown:
    async def test_kingdom_breakdown_present_in_response(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01")
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        assert "kingdom_breakdown" in resp.json()

    async def test_kingdom_breakdown_empty_when_no_ntcs(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        # No NTCs → early return, kingdom_breakdown not present but total_ntcs=0
        assert resp.json()["total_ntcs"] == 0

    async def test_bacteria_reads_tallied_correctly(self, fake_db):
        profile = [
            make_taxon(1743, "Cutibacterium acnes", 20, superkingdom="Bacteria"),
            make_taxon(329, "Ralstonia pickettii", 15, superkingdom="Bacteria"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 35
        assert entry["Viruses"] == 0
        assert entry["Eukaryota"] == 0

    async def test_viruses_reads_tallied_correctly(self, fake_db):
        profile = [
            make_taxon(129951, "Human mastadenovirus C", 12, superkingdom="Viruses"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Viruses"] == 12
        assert entry["Bacteria"] == 0

    async def test_multiple_kingdoms_split_correctly(self, fake_db):
        profile = [
            make_taxon(1743, "Cutibacterium acnes", 10, superkingdom="Bacteria"),
            make_taxon(129951, "Human mastadenovirus C", 5, superkingdom="Viruses"),
            make_taxon(4932, "Saccharomyces cerevisiae", 3, superkingdom="Eukaryota"),
            make_taxon(2188, "Methanobrevibacter smithii", 2, superkingdom="Archaea"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 10
        assert entry["Viruses"] == 5
        assert entry["Eukaryota"] == 3
        assert entry["Archaea"] == 2
        assert entry["Other"] == 0

    async def test_unknown_superkingdom_goes_to_other(self, fake_db):
        profile = [
            make_taxon(999999, "Unknown thing", 7, superkingdom="UnknownKingdom"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Other"] == 7

    async def test_null_superkingdom_goes_to_other(self, fake_db):
        # Taxon with no superkingdom set
        taxon = {
            "taxon_id": 999998,
            "name": "No kingdom taxon",
            "abundance": 4,
            "superkingdom": None,
            "rank": "species",
        }
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[taxon])
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Other"] == 4

    async def test_host_taxa_excluded_from_kingdom_breakdown(self, fake_db):
        profile = [
            make_taxon(9606, "Homo sapiens", 500, superkingdom="Eukaryota"),
            make_taxon(1743, "Cutibacterium acnes", 10, superkingdom="Bacteria"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        # Homo sapiens (9606) must not contribute to Eukaryota
        assert entry["Eukaryota"] == 0
        assert entry["Bacteria"] == 10

    async def test_all_host_taxon_ids_excluded_from_breakdown(self, fake_db):
        from app.constants import HOST_TAXON_IDS

        profile = [
            make_taxon(tid, f"host-{tid}", 100, superkingdom="Bacteria")
            for tid in HOST_TAXON_IDS
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 0
        assert entry["Other"] == 0

    async def test_non_kraken2_profiles_excluded_from_breakdown(self, fake_db):
        doc = {
            "sample_id": "NTC-1",
            "case_id_str": "case-1",
            "sample_type": "negative_ctrl",
            "material": "DNA",
            "order_date": "2026-04-01",
            "profiles": [
                {
                    "classifier": "centrifuge",
                    "profile": [
                        make_taxon(
                            1743, "Cutibacterium acnes", 50, superkingdom="Bacteria"
                        )
                    ],
                }
            ],
            "taxprofiler": {},
        }
        await fake_db["samples"].insert_one(doc)
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 0

    async def test_breakdown_entry_contains_required_keys(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01")
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert set(entry.keys()) == {
            "sample_id",
            "case_id",
            "order_date",
            "Bacteria",
            "Viruses",
            "Eukaryota",
            "Archaea",
            "Other",
        }

    async def test_breakdown_one_entry_per_ntc(self, fake_db):
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01"),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02"),
                make_ntc_doc("NTC-3", "case-3", "DNA", "2026-04-03"),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        assert len(resp.json()["kingdom_breakdown"]) == 3

    async def test_breakdown_sorted_by_order_date(self, fake_db):
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-B", "case-B", "DNA", "2026-04-10"),
                make_ntc_doc("NTC-A", "case-A", "DNA", "2026-04-01"),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        breakdown = resp.json()["kingdom_breakdown"]
        assert breakdown[0]["sample_id"] == "NTC-A"
        assert breakdown[1]["sample_id"] == "NTC-B"

    async def test_breakdown_empty_profile_yields_all_zeros(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[])
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 0
        assert entry["Viruses"] == 0
        assert entry["Eukaryota"] == 0
        assert entry["Archaea"] == 0
        assert entry["Other"] == 0


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestNtcTrendsResponseShape:
    async def test_response_contains_all_top_level_keys(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        data = resp.json()
        assert set(data.keys()) >= {
            "material",
            "window_days",
            "total_ntcs",
            "read_counts",
            "recurring_taxa",
        }

    async def test_min_case_count_present_when_ntcs_exist(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&min_case_pct=0.1")
        assert "min_case_count" in resp.json()

    async def test_min_case_count_is_at_least_one(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA&min_case_pct=0.0")
        assert resp.json()["min_case_count"] >= 1

    async def test_read_count_entry_shape(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["read_counts"][0]
        assert set(entry.keys()) == {
            "sample_id",
            "case_id",
            "order_date",
            "classified_reads",
        }

    async def test_recurring_taxon_entry_shape(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", "2026-04-01", profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "DNA", "2026-04-02", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        entry = resp.json()["recurring_taxa"][0]
        assert set(entry.keys()) >= {
            "taxon_id",
            "taxon_name",
            "superkingdom",
            "occurrences",
            "case_count",
        }
        assert isinstance(entry["occurrences"], list)
        occ = entry["occurrences"][0]
        assert set(occ.keys()) == {"case_id", "sample_id", "order_date", "abundance"}
