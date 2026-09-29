# tests/unit/test_metaval_models.py

from app.models.metaval import (
    MetavalDetailResponse,
    MetavalSummary,
    display_taxon_name,
)


def summary_doc(**overrides) -> dict:
    doc = {
        "_id": "64a1b2c3d4e5f6a7b8c9d0e1",
        "sample_id": "64a1b2c3d4e5f6a7b8c9d0e2",
        "classifier": "kraken2",
        "taxon_id": 10239,
        "taxon_name": "taxid_10239_Human-mastadenovirus-C",
    }
    doc.update(overrides)
    return doc


def detail_doc(**overrides) -> dict:
    doc = {
        **summary_doc(),
        "sample_name": "SRR001",
        "organisms": [
            {
                "organism_name": "Human-mastadenovirus-C",
                "igv_file_size_bytes": 100,
                "igv_too_large": False,
            }
        ],
        "blast": {"blastn": [], "blastx": []},
        "verification_data": {
            "type": "contigs",
            "count": 3,
            "avg_length": 1200.5,
            "available": True,
        },
    }
    doc.update(overrides)
    return doc


class TestDisplayTaxonName:
    def test_strips_taxid_prefix_and_dashes(self):
        assert (
            display_taxon_name("taxid_10239_Human-mastadenovirus-C")
            == "Human mastadenovirus C"
        )

    def test_old_format_name_only_replaces_dashes(self):
        assert display_taxon_name("Shigella-virus-Moo19") == "Shigella virus Moo19"

    def test_taxid_only_stripped_at_start(self):
        assert display_taxon_name("Foo-taxid_1_bar") == "Foo taxid_1_bar"


# Response shape, rejection of invalid documents and stripping of internal
# keys are covered end to end in tests/integration/test_metaval_router.py.
# Only cases no endpoint test reaches live here.


class TestMetavalSummary:
    def test_taxon_id_may_be_missing(self):
        doc = summary_doc()
        del doc["taxon_id"]
        assert MetavalSummary.model_validate(doc).taxon_id is None


class TestMetavalDetailResponse:
    def test_sample_id_may_be_unmapped(self):
        result = MetavalDetailResponse.model_validate(detail_doc(sample_id=None))
        assert result.sample_id is None
