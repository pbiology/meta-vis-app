# tests/unit/test_cases_helpers.py

from app.routers.cases import _non_host_total, _top_taxa_for, _host_pct_for, _spike_in_for


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(taxon_id, name, abundance, superkingdom=None):
    return {
        "taxon_id":    taxon_id,
        "name":        name,
        "abundance":   abundance,
        "superkingdom": superkingdom,
    }


def make_clf_qc(classified_reads=1000, unclassified_reads=200):
    return {
        "classified_reads":   classified_reads,
        "unclassified_reads": unclassified_reads,
    }


# Standard entries used across multiple tests
ENTRIES = [
    make_entry(1,    "root",           1000),        # root — excluded
    make_entry(9606, "Homo sapiens",   300,  "Eukaryota"),  # host — excluded
    make_entry(1279, "Staphylococcus", 400,  "Bacteria"),
    make_entry(1234, "Virus-A",        200,  "Viruses"),
    make_entry(5678, "Fungus-B",       100,  "Eukaryota"),
]


# ---------------------------------------------------------------------------
# _non_host_total
# ---------------------------------------------------------------------------

class TestNonHostTotal:

    def test_uses_clf_qc_classified_reads_when_available(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _non_host_total(ENTRIES, clf_qc)
        assert result == 1000 - 300  # classified - host

    def test_falls_back_to_root_reads_when_no_clf_qc(self):
        result = _non_host_total(ENTRIES, clf_qc=None)
        assert result == 1000 - 300  # root - host

    def test_no_host_entry_subtracts_zero(self):
        entries = [make_entry(1279, "Staphylococcus", 400, "Bacteria")]
        clf_qc = make_clf_qc(classified_reads=400)
        assert _non_host_total(entries, clf_qc) == 400

    def test_empty_entries_uses_classified_reads_from_clf_qc(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        assert _non_host_total([], clf_qc) == 1000

    def test_clf_qc_none_classified_reads_falls_back(self):
        clf_qc = {"classified_reads": None, "unclassified_reads": 200}
        result = _non_host_total(ENTRIES, clf_qc)
        # classified_reads is None so falls back to root reads
        assert result == 1000 - 300


# ---------------------------------------------------------------------------
# _top_taxa_for
# ---------------------------------------------------------------------------

class TestTopTaxaFor:

    def test_returns_top_n_by_abundance(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(ENTRIES, clf_qc, n=3)
        names = [r["name"] for r in result]
        assert names == ["Staphylococcus", "Virus-A", "Fungus-B"]

    def test_default_n_is_3(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(ENTRIES, clf_qc)
        assert len(result) <= 3

    def test_host_taxon_excluded(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(ENTRIES, clf_qc)
        names = [r["name"] for r in result]
        assert "Homo sapiens" not in names

    def test_root_excluded(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(ENTRIES, clf_qc)
        names = [r["name"] for r in result]
        assert "root" not in names

    def test_unclassified_excluded(self):
        entries = ENTRIES + [make_entry(0, "unclassified", 500)]
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(entries, clf_qc)
        names = [r["name"] for r in result]
        assert "unclassified" not in names

    def test_unclassified_prefix_excluded(self):
        entries = ENTRIES + [make_entry(999, "unclassified Bacteria", 500, "Bacteria")]
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(entries, clf_qc)
        names = [r["name"] for r in result]
        assert "unclassified Bacteria" not in names

    def test_pct_calculated_correctly(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(ENTRIES, clf_qc)
        staph = next(r for r in result if r["name"] == "Staphylococcus")
        non_host = 1000 - 300
        expected_pct = round(400 / non_host * 100, 3)
        assert staph["pct"] == expected_pct

    def test_pct_is_none_when_non_host_total_is_zero(self):
        entries = [make_entry(9606, "Homo sapiens", 1000, "Eukaryota")]
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _top_taxa_for(entries, clf_qc)
        assert result == []

    def test_empty_entries_returns_empty_list(self):
        assert _top_taxa_for([], make_clf_qc()) == []


# ---------------------------------------------------------------------------
# _host_pct_for
# ---------------------------------------------------------------------------

class TestHostPctFor:

    def test_happy_path_with_clf_qc(self):
        clf_qc = make_clf_qc(classified_reads=1000, unclassified_reads=200)
        result = _host_pct_for(ENTRIES, clf_qc)
        # total = host + unclassified = 300 + 200 = 500
        assert result == round(300 / 500 * 100, 1)

    def test_fallback_to_root_reads_when_no_clf_qc(self):
        result = _host_pct_for(ENTRIES, clf_qc=None)
        # total = classified = root = 1000
        assert result == round(300 / 1000 * 100, 1)

    def test_no_host_entry_zero_total_returns_none(self):
        entries = [make_entry(1279, "Staphylococcus", 400, "Bacteria")]
        clf_qc = make_clf_qc(classified_reads=400, unclassified_reads=0)
        # host_reads=0, total=0+0=0 — guard returns None
        result = _host_pct_for(entries, clf_qc)
        assert result is None

    def test_zero_total_returns_none(self):
        result = _host_pct_for([], make_clf_qc(classified_reads=0, unclassified_reads=0))
        assert result is None

    def test_empty_entries_returns_none(self):
        assert _host_pct_for([], None) is None


# ---------------------------------------------------------------------------
# _spike_in_for
# ---------------------------------------------------------------------------

class TestSpikeInFor:

    def test_empty_spike_in_ids_returns_empty_list(self):
        result = _spike_in_for(ENTRIES, spike_in_ids=set())
        assert result == []

    def test_returns_matching_spike_in_entries(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _spike_in_for(ENTRIES, spike_in_ids={1234}, clf_qc=clf_qc)
        assert len(result) == 1
        assert result[0]["name"] == "Virus-A"
        assert result[0]["taxon_id"] == 1234

    def test_no_matching_entries_returns_empty_list(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _spike_in_for(ENTRIES, spike_in_ids={9999}, clf_qc=clf_qc)
        assert result == []

    def test_pct_calculated_correctly(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _spike_in_for(ENTRIES, spike_in_ids={1234}, clf_qc=clf_qc)
        non_host = 1000 - 300
        expected_pct = round(200 / non_host * 100, 3)
        assert result[0]["pct"] == expected_pct

    def test_multiple_spike_ins_all_returned(self):
        clf_qc = make_clf_qc(classified_reads=1000)
        result = _spike_in_for(ENTRIES, spike_in_ids={1234, 5678}, clf_qc=clf_qc)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _non_host_total — diamond fallback (no root entry, no clf_qc)
# ---------------------------------------------------------------------------

class TestNonHostTotalDiamondFallback:

    def test_no_root_no_clf_qc_sums_non_host_entries(self):
        # Diamond doesn't emit a root entry and has no clf_qc
        entries = [
            make_entry(9606, "Homo sapiens",   300, "Eukaryota"),
            make_entry(1279, "Staphylococcus", 400, "Bacteria"),
            make_entry(1234, "Virus-A",        200, "Viruses"),
        ]
        result = _non_host_total(entries, clf_qc=None)
        # No root (taxon_id=1), so falls back to sum of non-host entries
        assert result == 400 + 200  # Staph + Virus, not Homo sapiens

    def test_no_root_no_clf_qc_excludes_unclassified(self):
        entries = [
            make_entry(0,    "unclassified",   500),
            make_entry(1279, "Staphylococcus", 400, "Bacteria"),
        ]
        result = _non_host_total(entries, clf_qc=None)
        assert result == 400  # unclassified excluded

    def test_no_root_no_clf_qc_excludes_unclassified_prefix(self):
        entries = [
            make_entry(999,  "unclassified Bacteria", 500, "Bacteria"),
            make_entry(1279, "Staphylococcus",         400, "Bacteria"),
        ]
        result = _non_host_total(entries, clf_qc=None)
        assert result == 400

    def test_no_root_no_clf_qc_empty_entries_returns_zero(self):
        assert _non_host_total([], clf_qc=None) == 0

    def test_root_present_takes_priority_over_sum_fallback(self):
        # When root IS present, use it rather than summing
        entries = [
            make_entry(1,    "root",           1000),
            make_entry(9606, "Homo sapiens",   300, "Eukaryota"),
            make_entry(1279, "Staphylococcus", 400, "Bacteria"),
        ]
        result = _non_host_total(entries, clf_qc=None)
        assert result == 1000 - 300  # root - host, not sum