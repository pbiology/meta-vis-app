# tests/unit/test_constants.py

from app.constants import HOST_TAXON_IDS


class TestHostTaxonIds:
    def test_is_frozenset(self):
        assert isinstance(HOST_TAXON_IDS, frozenset)

    def test_contains_unclassified(self):
        assert 0 in HOST_TAXON_IDS

    def test_contains_root(self):
        assert 1 in HOST_TAXON_IDS

    def test_contains_cellular_organisms(self):
        assert 131567 in HOST_TAXON_IDS

    def test_contains_homo_sapiens(self):
        assert 9606 in HOST_TAXON_IDS

    def test_does_not_contain_bacteria(self):
        assert 2 not in HOST_TAXON_IDS

    def test_does_not_contain_arbitrary_taxon(self):
        assert 1743 not in HOST_TAXON_IDS

    def test_immutable(self):
        # frozenset must not support add/remove
        try:
            HOST_TAXON_IDS.add(999)  # type: ignore[attr-defined]
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass