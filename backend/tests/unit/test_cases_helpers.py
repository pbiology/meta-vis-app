# tests/unit/test_cases_helpers.py

from app.taxonomy_utils import read_totals
from app.routers.analyses import (
    _top_taxa_for,
    _spike_in_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entry(taxon_id, name, abundance, superkingdom=None):
    return {
        "taxon_id": taxon_id,
        "name": name,
        "abundance": abundance,
        "superkingdom": superkingdom,
    }


def make_clf_qc(classified_reads=1000, unclassified_reads=200):
    return {
        "classified_reads": classified_reads,
        "unclassified_reads": unclassified_reads,
    }


# Standard entries used across multiple tests. Counts are DIRECT, as taxpasta
# writes them: root holds only what could not be placed deeper, so the profile
# sums to 2000 classified reads rather than root's 1000.
ENTRIES = [
    make_entry(1, "root", 1000),  # structural node — never a finding
    make_entry(9606, "Homo sapiens", 300, "Eukaryota"),  # host
    make_entry(1279, "Staphylococcus", 400, "Bacteria"),
    make_entry(1234, "Virus-A", 200, "Viruses"),
    make_entry(5678, "Fungus-B", 100, "Eukaryota"),
]

# Shaped like real Kraken2 output, where host dwarfs root. The old root-based
# fallback returned a negative non-host total for profiles like this.
HOST_HEAVY_ENTRIES = [
    make_entry(0, "unclassified", 1_000_000),
    make_entry(1, "root", 2_700_000),
    make_entry(131567, "cellular organisms", 50_000),
    make_entry(543, "Enterobacteriaceae", 4_350_000, "Bacteria"),
    make_entry(9606, "Homo sapiens", 17_500_000, "Eukaryota"),
    make_entry(11676, "HIV-1", 250, "Viruses"),
]


# ---------------------------------------------------------------------------
# read_totals
# ---------------------------------------------------------------------------


class TestReadTotals:
    def test_uses_clf_qc_classified_reads_when_available(self):
        totals = read_totals(ENTRIES, make_clf_qc(classified_reads=1000))
        assert totals.classified == 1000
        assert totals.non_host == 1000 - 300

    def test_sums_direct_counts_when_no_clf_qc(self):
        totals = read_totals(ENTRIES, clf_qc=None)
        # Every entry except unclassified — not root's 1000.
        assert totals.classified == 2000
        assert totals.unclassified == 0
        assert totals.non_host == 2000 - 300

    def test_root_is_an_ordinary_entry_not_the_classified_total(self):
        totals = read_totals(HOST_HEAVY_ENTRIES, clf_qc=None)
        assert totals.classified == 24_600_250
        assert totals.unclassified == 1_000_000
        assert totals.total == 25_600_250
        # Root (2.7M) minus host (17.5M) used to make this negative.
        assert totals.non_host == 7_100_250
        assert totals.host_exceeds_classified is False

    def test_clf_qc_none_classified_reads_falls_back_to_the_profile(self):
        clf_qc = {"classified_reads": None, "unclassified_reads": 200}
        totals = read_totals(ENTRIES, clf_qc)
        assert totals.classified == 2000
        assert totals.unclassified == 200

    def test_unclassified_prefix_counts_as_classified(self):
        # "unclassified Bacteria" is a real NCBI taxon holding placed reads;
        # only taxon 0 is unplaced.
        entries = [
            make_entry(0, "unclassified", 500),
            make_entry(999, "unclassified Bacteria", 300, "Bacteria"),
            make_entry(1279, "Staphylococcus", 400, "Bacteria"),
        ]
        totals = read_totals(entries, clf_qc=None)
        assert totals.classified == 700
        assert totals.unclassified == 500

    def test_no_host_entry_subtracts_zero(self):
        entries = [make_entry(1279, "Staphylococcus", 400, "Bacteria")]
        totals = read_totals(entries, make_clf_qc(classified_reads=400))
        assert totals.non_host == 400

    def test_empty_entries_uses_classified_reads_from_clf_qc(self):
        totals = read_totals([], make_clf_qc(classified_reads=1000))
        assert totals.non_host == 1000

    def test_empty_entries_and_no_clf_qc_is_all_zero(self):
        totals = read_totals([], clf_qc=None)
        assert totals.classified == 0
        assert totals.non_host == 0
        assert totals.host_exceeds_classified is False

    def test_host_above_classified_is_clamped_and_flagged(self):
        # QC contradicts the profile: report it rather than serve a negative.
        totals = read_totals(HOST_HEAVY_ENTRIES, make_clf_qc(classified_reads=1000))
        assert totals.non_host == 0
        assert totals.host_exceeds_classified is True

    def test_missing_abundance_is_treated_as_zero(self):
        entries = [{"taxon_id": 1279, "name": "Staphylococcus"}]
        assert read_totals(entries, clf_qc=None).classified == 0


# ---------------------------------------------------------------------------
# read_totals.host_pct
# ---------------------------------------------------------------------------


class TestHostPct:
    def test_divides_by_everything_the_classifier_processed(self):
        totals = read_totals(
            ENTRIES, make_clf_qc(classified_reads=1000, unclassified_reads=200)
        )
        # 300 of 1200 reads. The old denominator was host + unclassified,
        # which reported 60% for this sample.
        assert totals.host_pct == 25.0

    def test_falls_back_to_the_profile_when_no_clf_qc(self):
        totals = read_totals(ENTRIES, clf_qc=None)
        # 300 of 2000 classified, with no unclassified row in the profile.
        assert totals.host_pct == 15.0

    def test_counts_the_unclassified_row_when_qc_is_absent(self):
        entries = ENTRIES + [make_entry(0, "unclassified", 500)]
        totals = read_totals(entries, clf_qc=None)
        assert totals.host_pct == round(300 / 2500 * 100, 1)

    def test_no_host_entry_is_zero_pct(self):
        entries = [make_entry(1279, "Staphylococcus", 400, "Bacteria")]
        totals = read_totals(entries, make_clf_qc(400, unclassified_reads=0))
        assert totals.host_pct == 0.0

    def test_zero_total_returns_none(self):
        totals = read_totals([], make_clf_qc(classified_reads=0, unclassified_reads=0))
        assert totals.host_pct is None

    def test_empty_entries_returns_none(self):
        assert read_totals([], None).host_pct is None


# ---------------------------------------------------------------------------
# _top_taxa_for
# ---------------------------------------------------------------------------

# The denominator the router passes in for ENTRIES with standard QC.
NON_HOST = 1000 - 300


class TestTopTaxaFor:
    def test_returns_top_n_by_abundance(self):
        result = _top_taxa_for(ENTRIES, NON_HOST, n=3)
        names = [r["name"] for r in result]
        assert names == ["Staphylococcus", "Virus-A", "Fungus-B"]

    def test_default_n_is_3(self):
        assert len(_top_taxa_for(ENTRIES, NON_HOST)) <= 3

    def test_host_taxon_excluded(self):
        names = [r["name"] for r in _top_taxa_for(ENTRIES, NON_HOST)]
        assert "Homo sapiens" not in names

    def test_root_excluded(self):
        names = [r["name"] for r in _top_taxa_for(ENTRIES, NON_HOST)]
        assert "root" not in names

    def test_unclassified_excluded(self):
        entries = ENTRIES + [make_entry(0, "unclassified", 500)]
        names = [r["name"] for r in _top_taxa_for(entries, NON_HOST)]
        assert "unclassified" not in names

    def test_unclassified_prefix_excluded(self):
        # Dropped from the list even though read_totals counts it in the
        # denominator: a hit that vague is not a finding.
        entries = ENTRIES + [make_entry(999, "unclassified Bacteria", 500, "Bacteria")]
        names = [r["name"] for r in _top_taxa_for(entries, NON_HOST)]
        assert "unclassified Bacteria" not in names

    def test_pct_calculated_correctly(self):
        result = _top_taxa_for(ENTRIES, NON_HOST)
        staph = next(r for r in result if r["name"] == "Staphylococcus")
        assert staph["pct"] == round(400 / NON_HOST * 100, 3)

    def test_pct_is_none_when_total_is_zero(self):
        entries = [make_entry(1279, "Staphylococcus", 400, "Bacteria")]
        result = _top_taxa_for(entries, total=0)
        assert result[0]["pct"] is None

    def test_host_only_profile_returns_empty_list(self):
        entries = [make_entry(9606, "Homo sapiens", 1000, "Eukaryota")]
        assert _top_taxa_for(entries, total=700) == []

    def test_empty_entries_returns_empty_list(self):
        assert _top_taxa_for([], NON_HOST) == []


# ---------------------------------------------------------------------------
# _spike_in_for
# ---------------------------------------------------------------------------


class TestSpikeInFor:
    def test_empty_spike_in_ids_returns_empty_list(self):
        assert _spike_in_for(ENTRIES, spike_in_ids=set(), total=NON_HOST) == []

    def test_returns_matching_spike_in_entries(self):
        result = _spike_in_for(ENTRIES, spike_in_ids={1234}, total=NON_HOST)
        assert len(result) == 1
        assert result[0]["name"] == "Virus-A"
        assert result[0]["taxon_id"] == 1234

    def test_no_matching_entries_returns_empty_list(self):
        assert _spike_in_for(ENTRIES, spike_in_ids={9999}, total=NON_HOST) == []

    def test_pct_calculated_correctly(self):
        result = _spike_in_for(ENTRIES, spike_in_ids={1234}, total=NON_HOST)
        assert result[0]["pct"] == round(200 / NON_HOST * 100, 3)

    def test_multiple_spike_ins_all_returned(self):
        result = _spike_in_for(ENTRIES, spike_in_ids={1234, 5678}, total=NON_HOST)
        assert len(result) == 2
