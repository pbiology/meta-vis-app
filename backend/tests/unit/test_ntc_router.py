# tests/unit/test_ntc_router.py
#
# Tests for the NTC trends router.
# Uses mongomock_motor for an in-memory MongoDB — the same pattern as the
# integration tests — because the router performs real query + aggregation
# logic that is worth testing end-to-end without a live database.
#
# asyncio_mode = "auto" is set in pyproject.toml, so all async test methods
# are picked up automatically by pytest-asyncio without any extra decoration.

from datetime import date, timedelta

import pytest
from bson import ObjectId
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


# ---------------------------------------------------------------------------
# Fixture dates
#
# The NTC endpoints filter on `order_date >= today - window_days` (default 90),
# so fixtures pinned to absolute dates silently age out of the window: every
# query then returns nothing and the assertions below start reading empty
# lists. These offsets keep the same relative spacing as the original
# 2026-04-01 / -02 / -03 / -10 fixtures, so the ordering assertions still hold,
# while staying well inside the smallest window the tests exercise (30 days).
# ---------------------------------------------------------------------------


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


DAY_1 = _days_ago(20)
DAY_2 = _days_ago(19)
DAY_3 = _days_ago(18)
DAY_10 = _days_ago(11)
# Far enough back to fall outside any window the tests use.
OUT_OF_WINDOW = _days_ago(400)


def make_ntc_doc(
    sample_id: str,
    case_id: str,
    nucleic_acid: str,
    order_date: str,
    profile: list[dict] | None = None,
    classified_reads: int | None = None,
    analysis_id: str | None = None,
    ingested_at: str | None = None,
    pipeline: str = "taxprofiler",
) -> dict:
    """Build a minimal sample document as stored in MongoDB."""
    doc: dict = {
        "sample_id": sample_id,
        "case_id": case_id,
        "sample_type": "negative_ctrl",
        "is_latest_analysis": True,
        "nucleic_acid": nucleic_acid,
        "order_date": order_date,
        "profiles": [],
        "taxprofiler": {},
    }
    if pipeline == "trana":
        # The two stats blocks are mutually exclusive in real documents, and
        # the trends query now scopes on which one is present.
        del doc["taxprofiler"]
        doc["trana"] = {}
    if analysis_id is not None:
        doc["analysis_id"] = analysis_id
    if ingested_at is not None:
        doc["ingested_at"] = ingested_at
    if profile is not None:
        doc["profiles"] = [{"classifier": "kraken2", "profile": profile}]
    if classified_reads is not None:
        if pipeline == "trana":
            doc["trana"] = {"nanoplot_processed": {"number_of_reads": classified_reads}}
        else:
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
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ntcs"] == 0
        assert data["read_counts"] == []
        assert data["recurring_taxa"] == []

    async def test_no_ntcs_response_contains_nucleic_acid_and_window(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=RNA&window_days=30")
        data = resp.json()
        assert data["nucleic_acid"] == "RNA"
        assert data["window_days"] == 30

    async def test_dna_ntcs_not_returned_for_rna_query(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=RNA")
        assert resp.json()["total_ntcs"] == 0

    async def test_non_ntc_samples_excluded(self, fake_db):
        doc = make_ntc_doc("S-1", "case-1", "DNA", DAY_1)
        doc["sample_type"] = "sample"
        await fake_db["samples"].insert_one(doc)
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        assert resp.json()["total_ntcs"] == 0


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestNtcTrendsValidation:
    async def test_missing_nucleic_acid_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends")
        assert resp.status_code == 422

    async def test_invalid_nucleic_acid_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=INVALID")
        assert resp.status_code == 422

    async def test_window_days_below_minimum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA&window_days=6")
        assert resp.status_code == 422

    async def test_window_days_above_maximum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&window_days=366"
        )
        assert resp.status_code == 422

    async def test_min_reads_below_minimum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=0")
        assert resp.status_code == 422

    async def test_min_control_pct_above_maximum_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_control_pct=1.1"
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Read counts
# ---------------------------------------------------------------------------


class TestNtcReadCounts:
    async def test_classified_reads_from_multiqc_qc_field(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, classified_reads=500)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        counts = resp.json()["read_counts"]
        assert len(counts) == 1
        assert counts[0]["classified_reads"] == 500
        assert counts[0]["sample_id"] == "NTC-1"
        assert counts[0]["case_ids"] == ["case-1"]

    async def test_classified_reads_fallback_sums_the_profile(self, fake_db):
        profile = [
            make_taxon(1, "root", 300),
            make_taxon(1743, "Cutibacterium acnes", 25),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        counts = resp.json()["read_counts"]
        # Every placed read, not root's 300 — taxpasta counts are direct.
        assert counts[0]["classified_reads"] == 325

    async def test_classified_reads_fallback_excludes_unclassified(self, fake_db):
        # A host-heavy profile of the shape Kraken2 actually produces: root is
        # a fraction of the total, so reporting it under-counted the control.
        profile = [
            make_taxon(0, "unclassified", 1000),
            make_taxon(1, "root", 300),
            make_taxon(9606, "Homo sapiens", 8000, superkingdom="Eukaryota"),
            make_taxon(1743, "Cutibacterium acnes", 25),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["classified_reads"] == 8325

    async def test_classified_reads_null_when_no_qc_and_no_profile(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["classified_reads"] is None

    async def test_read_counts_sorted_by_order_date(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-B", "case-B", "DNA", DAY_10, classified_reads=200)
        )
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-A", "case-A", "DNA", DAY_1, classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        counts = resp.json()["read_counts"]
        assert counts[0]["sample_id"] == "NTC-A"
        assert counts[1]["sample_id"] == "NTC-B"

    async def test_ntc_outside_window_excluded_from_read_counts(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc(
                "NTC-OLD", "case-old", "DNA", OUT_OF_WINDOW, classified_reads=999
            )
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA&window_days=90")
        assert resp.json()["total_ntcs"] == 0


# ---------------------------------------------------------------------------
# Recurring taxa — filtering logic
# ---------------------------------------------------------------------------


class TestRecurringTaxa:
    async def test_taxon_above_min_reads_in_multiple_cases_is_recurring(self, fake_db):
        contaminant = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[contaminant]),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[contaminant]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert len(taxa) == 1
        assert taxa[0]["taxon_id"] == 1743
        assert taxa[0]["taxon_name"] == "Cutibacterium acnes"
        assert taxa[0]["control_count"] == 2

    async def test_taxon_at_or_below_min_reads_excluded(self, fake_db):
        # abundance=3, min_reads=3 — must be strictly greater than
        low = make_taxon(1743, "Cutibacterium acnes", 3)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[low]),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[low]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []

    async def test_taxon_above_min_reads_threshold(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 4)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        assert len(resp.json()["recurring_taxa"]) == 1

    async def test_host_taxon_ids_excluded_from_recurring_taxa(self, fake_db):
        host = make_taxon(9606, "Homo sapiens", 100, superkingdom="Eukaryota")
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[host]),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[host]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=1&min_control_pct=0.1"
        )
        taxon_ids = [t["taxon_id"] for t in resp.json()["recurring_taxa"]]
        assert 9606 not in taxon_ids

    async def test_all_host_taxon_ids_excluded(self, fake_db):
        from app.constants import HOST_TAXON_IDS

        host_entries = [make_taxon(tid, f"host-{tid}", 100) for tid in HOST_TAXON_IDS]
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=host_entries),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=host_entries),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=1&min_control_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []

    async def test_taxon_in_single_case_excluded_when_min_control_pct_requires_more(
        self, fake_db
    ):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        # 10 NTCs, taxon in only 1 control; threshold = max(1, round(10*0.5)) = 5
        docs = [
            make_ntc_doc(f"NTC-{i}", f"case-{i}", "DNA", DAY_1) for i in range(9)
        ] + [make_ntc_doc("NTC-9", "case-9", "DNA", DAY_1, profile=[taxon])]
        await fake_db["samples"].insert_many(docs)
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.5"
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
                    DAY_1,
                    profile=profile_with_duplicate,
                ),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert len(taxa) == 1
        assert taxa[0]["control_count"] == 2

    async def test_recurring_taxa_sorted_by_control_count_descending(self, fake_db):
        taxon_a = make_taxon(1743, "Taxon-A", 10)
        taxon_b = make_taxon(329, "Taxon-B", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1", "case-1", "DNA", DAY_1, profile=[taxon_a, taxon_b]
                ),
                make_ntc_doc(
                    "NTC-2", "case-2", "DNA", DAY_2, profile=[taxon_a, taxon_b]
                ),
                make_ntc_doc("NTC-3", "case-3", "DNA", DAY_3, profile=[taxon_b]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        taxa = resp.json()["recurring_taxa"]
        assert taxa[0]["taxon_id"] == 329  # Taxon-B — 3 cases
        assert taxa[1]["taxon_id"] == 1743  # Taxon-A — 2 cases

    async def test_occurrences_sorted_by_order_date(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-B", "case-B", "DNA", DAY_10, profile=[taxon]),
                make_ntc_doc("NTC-A", "case-A", "DNA", DAY_1, profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        occ = resp.json()["recurring_taxa"][0]["occurrences"]
        assert occ[0]["order_date"] == DAY_1
        assert occ[1]["order_date"] == DAY_10

    async def test_non_kraken2_profiles_ignored(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        docs = [
            {
                "sample_id": "NTC-1",
                "case_id": "case-1",
                "sample_type": "negative_ctrl",
                "is_latest_analysis": True,
                "nucleic_acid": "DNA",
                "order_date": DAY_1,
                "profiles": [{"classifier": "centrifuge", "profile": [taxon]}],
                "taxprofiler": {},
            },
            {
                "sample_id": "NTC-2",
                "case_id": "case-2",
                "sample_type": "negative_ctrl",
                "is_latest_analysis": True,
                "nucleic_acid": "DNA",
                "order_date": DAY_2,
                "profiles": [{"classifier": "centrifuge", "profile": [taxon]}],
                "taxprofiler": {},
            },
        ]
        await fake_db["samples"].insert_many(docs)
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        assert resp.json()["recurring_taxa"] == []


# ---------------------------------------------------------------------------
# Kingdom breakdown
# ---------------------------------------------------------------------------


class TestKingdomBreakdown:
    async def test_kingdom_breakdown_present_in_response(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        assert "kingdom_breakdown" in resp.json()

    async def test_kingdom_breakdown_empty_when_no_ntcs(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        # No NTCs → early return, kingdom_breakdown not present but total_ntcs=0
        assert resp.json()["total_ntcs"] == 0

    async def test_bacteria_reads_tallied_correctly(self, fake_db):
        profile = [
            make_taxon(1743, "Cutibacterium acnes", 20, superkingdom="Bacteria"),
            make_taxon(329, "Ralstonia pickettii", 15, superkingdom="Bacteria"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 35
        assert entry["Viruses"] == 0
        assert entry["Eukaryota"] == 0

    async def test_viruses_reads_tallied_correctly(self, fake_db):
        profile = [
            make_taxon(129951, "Human mastadenovirus C", 12, superkingdom="Viruses"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
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
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
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
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
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
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[taxon])
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Other"] == 4

    async def test_host_taxa_excluded_from_kingdom_breakdown(self, fake_db):
        profile = [
            make_taxon(9606, "Homo sapiens", 500, superkingdom="Eukaryota"),
            make_taxon(1743, "Cutibacterium acnes", 10, superkingdom="Bacteria"),
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
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
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 0
        assert entry["Other"] == 0

    async def test_non_kraken2_profiles_excluded_from_breakdown(self, fake_db):
        doc = {
            "sample_id": "NTC-1",
            "case_id": "case-1",
            "sample_type": "negative_ctrl",
            "is_latest_analysis": True,
            "nucleic_acid": "DNA",
            "order_date": DAY_1,
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
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert entry["Bacteria"] == 0

    async def test_breakdown_entry_contains_required_keys(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        assert set(entry.keys()) == {
            "sample_id",
            "case_ids",
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
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2),
                make_ntc_doc("NTC-3", "case-3", "DNA", DAY_3),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        assert len(resp.json()["kingdom_breakdown"]) == 3

    async def test_breakdown_sorted_by_order_date(self, fake_db):
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-B", "case-B", "DNA", DAY_10),
                make_ntc_doc("NTC-A", "case-A", "DNA", DAY_1),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        breakdown = resp.json()["kingdom_breakdown"]
        assert breakdown[0]["sample_id"] == "NTC-A"
        assert breakdown[1]["sample_id"] == "NTC-B"

    async def test_breakdown_empty_profile_yields_all_zeros(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[])
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
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
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        data = resp.json()
        assert set(data.keys()) >= {
            "nucleic_acid",
            "window_days",
            "total_ntcs",
            "read_counts",
            "recurring_taxa",
        }

    async def test_min_control_count_present_when_ntcs_exist(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_control_pct=0.1"
        )
        assert "min_control_count" in resp.json()

    async def test_min_control_count_is_at_least_one(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_control_pct=0.0"
        )
        assert resp.json()["min_control_count"] >= 1

    async def test_read_count_entry_shape(self, fake_db):
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, classified_reads=100)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")
        entry = resp.json()["read_counts"][0]
        assert set(entry.keys()) == {
            "sample_id",
            "case_ids",
            "order_date",
            "classified_reads",
        }

    async def test_recurring_taxon_entry_shape(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "DNA", DAY_1, profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "DNA", DAY_2, profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1"
        )
        entry = resp.json()["recurring_taxa"][0]
        assert set(entry.keys()) >= {
            "taxon_id",
            "taxon_name",
            "superkingdom",
            "occurrences",
            "control_count",
        }
        assert isinstance(entry["occurrences"], list)
        occ = entry["occurrences"][0]
        assert set(occ.keys()) == {
            "case_ids",
            "sample_id",
            "order_date",
            "abundance",
        }


# ---------------------------------------------------------------------------
# Shared controls
#
# One physical NTC is sequenced alongside every case in its run, so it reaches
# the database once per case with the same sample_id. Everything the trends
# page reports counts the control, not the documents.
# ---------------------------------------------------------------------------


def shared_control_docs(
    sample_id: str = "NTC-260305-DNA",
    cases: tuple[str, ...] = ("case-a", "case-b", "case-c"),
    order_date: str = DAY_1,
    **kwargs,
) -> list[dict]:
    """One control as it really arrives: the same sample_id under N cases."""
    return [
        make_ntc_doc(sample_id, case_id, "DNA", order_date, **kwargs)
        for case_id in cases
    ]


class TestSharedControlIsCountedOnce:
    async def test_total_ntcs_counts_controls_not_documents(self, fake_db):
        await fake_db["samples"].insert_many(shared_control_docs())
        app = make_app(fake_db)

        resp = TestClient(app).get("/api/v1/ntc/trends?nucleic_acid=DNA")

        assert resp.json()["total_ntcs"] == 1

    async def test_read_counts_plot_one_point_per_control(self, fake_db):
        await fake_db["samples"].insert_many(
            shared_control_docs(classified_reads=11032789)
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert len(counts) == 1
        assert counts[0]["classified_reads"] == 11032789

    async def test_read_count_lists_every_case_for_drill_down(self, fake_db):
        await fake_db["samples"].insert_many(shared_control_docs(classified_reads=500))
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["case_ids"] == ["case-a", "case-b", "case-c"]

    async def test_kingdom_breakdown_has_one_entry_per_control(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 50, superkingdom="Bacteria")
        await fake_db["samples"].insert_many(shared_control_docs(profile=[taxon]))
        app = make_app(fake_db)

        breakdown = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["kingdom_breakdown"]
        )

        assert len(breakdown) == 1
        # The tally is one case's, never the sum across the copies.
        assert breakdown[0]["Bacteria"] == 50

    async def test_threshold_denominator_counts_controls(self, fake_db):
        # Ten documents, two controls. A denominator of 10 would put the
        # threshold at 5 and hide a taxon present in both controls.
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            shared_control_docs(
                "NTC-A", ("c1", "c2", "c3", "c4", "c5"), DAY_1, profile=[taxon]
            )
            + shared_control_docs(
                "NTC-B", ("c6", "c7", "c8", "c9", "c10"), DAY_2, profile=[taxon]
            )
        )
        app = make_app(fake_db)

        body = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.5")
            .json()
        )

        assert body["total_ntcs"] == 2
        assert body["min_control_count"] == 1
        assert [t["taxon_id"] for t in body["recurring_taxa"]] == [1743]

    async def test_taxon_in_one_shared_control_counts_one(self, fake_db):
        # The headline regression: a taxon in a single control that happens to
        # be bundled into seven cases reported control_count 7.
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            shared_control_docs(
                "NTC-A", tuple(f"case-{i}" for i in range(7)), DAY_1, profile=[taxon]
            )
        )
        app = make_app(fake_db)

        taxa = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1")
            .json()["recurring_taxa"]
        )

        assert taxa[0]["control_count"] == 1
        assert len(taxa[0]["occurrences"]) == 1
        assert taxa[0]["occurrences"][0]["case_ids"] == [f"case-{i}" for i in range(7)]

    async def test_taxon_in_two_controls_counts_two(self, fake_db):
        taxon = make_taxon(1743, "Cutibacterium acnes", 10)
        await fake_db["samples"].insert_many(
            shared_control_docs("NTC-A", ("c1", "c2"), DAY_1, profile=[taxon])
            + shared_control_docs("NTC-B", ("c3", "c4"), DAY_2, profile=[taxon])
        )
        app = make_app(fake_db)

        taxa = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA&min_reads=3&min_control_pct=0.1")
            .json()["recurring_taxa"]
        )

        assert taxa[0]["control_count"] == 2
        assert len(taxa[0]["occurrences"]) == 2

    async def test_profile_fallback_is_not_multiplied_by_copy_count(self, fake_db):
        # No classified_reads, so the read count falls back to summing the
        # profile. Summed across the copies it came out 3x too high.
        taxon = make_taxon(1743, "Cutibacterium acnes", 1000)
        await fake_db["samples"].insert_many(shared_control_docs(profile=[taxon]))
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["classified_reads"] == 1000


class TestControlDateIsStable:
    async def test_control_is_plotted_at_its_own_date(self, fake_db):
        await fake_db["samples"].insert_many(
            shared_control_docs(order_date=DAY_2, classified_reads=500)
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["order_date"] == DAY_2

    async def test_date_does_not_move_when_copies_disagree(self, fake_db):
        # Data ingested before a control could carry its own date inherited each
        # case's. The earliest is served: it is the only choice that cannot
        # shift as analyses are added.
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-A", "case-late", "DNA", DAY_3, classified_reads=5),
                make_ntc_doc("NTC-A", "case-early", "DNA", DAY_1, classified_reads=5),
            ]
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert len(counts) == 1
        assert counts[0]["order_date"] == DAY_1


class TestNewestAnalysisWins:
    async def test_highest_analysis_version_supplies_the_values(self, fake_db):
        older = "6a9ea6568c6197583da39320"
        newer = "6a9ea6568c6197583da39321"
        await fake_db["case_analysis"].insert_many(
            [
                {"_id": ObjectId(older), "case_id": "case-a", "version": 1},
                {"_id": ObjectId(newer), "case_id": "case-b", "version": 3},
            ]
        )
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-A",
                    "case-a",
                    "DNA",
                    DAY_1,
                    classified_reads=100,
                    analysis_id=older,
                ),
                make_ntc_doc(
                    "NTC-A",
                    "case-b",
                    "DNA",
                    DAY_1,
                    classified_reads=999,
                    analysis_id=newer,
                ),
            ]
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["classified_reads"] == 999

    async def test_ingested_at_breaks_a_version_tie(self, fake_db):
        # Versions are per case, so copies from different cases tie routinely.
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-A",
                    "case-a",
                    "DNA",
                    DAY_1,
                    classified_reads=100,
                    ingested_at="2026-09-07 11:53:46",
                ),
                make_ntc_doc(
                    "NTC-A",
                    "case-b",
                    "DNA",
                    DAY_1,
                    classified_reads=999,
                    ingested_at="2026-09-17 08:26:04",
                ),
            ]
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["classified_reads"] == 999

    async def test_value_missing_on_the_newest_copy_falls_back(self, fake_db):
        # The newest copy has no read count at all; reporting a gap would be
        # worse than serving the older run's number.
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-A",
                    "case-old",
                    "DNA",
                    DAY_1,
                    classified_reads=100,
                    ingested_at="2026-09-01 10:00:00",
                ),
                make_ntc_doc(
                    "NTC-A",
                    "case-new",
                    "DNA",
                    DAY_1,
                    ingested_at="2026-09-17 10:00:00",
                ),
            ]
        )
        app = make_app(fake_db)

        counts = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA")
            .json()["read_counts"]
        )

        assert counts[0]["classified_reads"] == 100


class TestPipelineScoping:
    async def test_trana_control_excluded_from_taxprofiler_totals(self, fake_db):
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-TP", "case-a", "DNA", DAY_1, classified_reads=500),
                make_ntc_doc(
                    "16SNEGABC123",
                    "case-b",
                    "DNA",
                    DAY_2,
                    classified_reads=1000,
                    pipeline="trana",
                ),
            ]
        )
        app = make_app(fake_db)

        body = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA&pipeline=taxprofiler")
            .json()
        )

        assert body["total_ntcs"] == 1
        assert [c["sample_id"] for c in body["read_counts"]] == ["NTC-TP"]

    async def test_taxprofiler_control_excluded_from_trana_totals(self, fake_db):
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-TP", "case-a", "DNA", DAY_1, classified_reads=500),
                make_ntc_doc(
                    "16SNEGABC123",
                    "case-b",
                    "DNA",
                    DAY_2,
                    classified_reads=1000,
                    pipeline="trana",
                ),
            ]
        )
        app = make_app(fake_db)

        body = (
            TestClient(app)
            .get("/api/v1/ntc/trends?nucleic_acid=DNA&pipeline=trana")
            .json()
        )

        assert body["total_ntcs"] == 1
        assert body["read_counts"][0]["sample_id"] == "16SNEGABC123"
        assert body["read_counts"][0]["classified_reads"] == 1000
