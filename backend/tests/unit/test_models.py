# tests/unit/test_models.py

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.sample import (
    SampleResponse,
    CaseResponse,
    SampleMetadata,
    ClassifierQcStats,
    PipelineConfiguration,
    ReviewStatus,
    TaxonEntry,
    ClassifierProfile,
)


def minimal_sample_doc(**overrides) -> dict:
    doc = {
        "case_id": "64a1b2c3d4e5f6a7b8c9d0e2",
        "sample_id": "SRR001",
        "sample_source": "N/A",
        "sample_type": "sample",
        "material": "DNA",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    doc.update(overrides)
    return doc


def minimal_case_doc(**overrides) -> dict:
    doc = {
        "case_id": "speedysnake",
        "ingested_at": datetime.now(timezone.utc),
    }
    doc.update(overrides)
    return doc


class TestSampleResponse:
    def test_minimal_valid_document(self):
        result = SampleResponse.model_validate(minimal_sample_doc())
        assert result.sample_type == "sample"
        assert result.material == "DNA"

    def test_extra_fields_are_allowed(self):
        doc = minimal_sample_doc(top_taxa={"kraken2": []}, host_pct={"kraken2": 12.5})
        dump = SampleResponse.model_validate(doc).model_dump(mode="json")
        assert dump["top_taxa"] == {"kraken2": []}

    def test_unknown_extra_fields_do_not_raise(self):
        SampleResponse.model_validate(minimal_sample_doc(future_field="value"))

    def test_invalid_sample_type_raises(self):
        with pytest.raises(ValidationError):
            SampleResponse.model_validate(minimal_sample_doc(sample_type="test"))

    def test_invalid_material_raises(self):
        with pytest.raises(ValidationError):
            SampleResponse.model_validate(minimal_sample_doc(material="protein"))

    def test_all_valid_sample_types_accepted(self):
        for t in ("sample", "positive_ctrl", "negative_ctrl"):
            assert (
                SampleResponse.model_validate(
                    minimal_sample_doc(sample_type=t)
                ).sample_type
                == t
            )

    def test_both_materials_accepted(self):
        for m in ("DNA", "RNA"):
            assert (
                SampleResponse.model_validate(minimal_sample_doc(material=m)).material
                == m
            )

    def test_defaults_applied_when_fields_absent(self):
        result = SampleResponse.model_validate(minimal_sample_doc())
        assert result.has_krona is False
        assert result.profiles == []
        assert result.review.reviewed is False
        assert result.subject_id is None

    def test_nested_taxprofiler_validates(self):
        doc = minimal_sample_doc(
            taxprofiler={
                "fastp": {"total_reads_before_filtering": 1000000},
                "classifiers": {
                    "kraken2": {"pct_unclassified": 5.0, "classified_reads": 950000}
                },
            }
        )
        result = SampleResponse.model_validate(doc)
        assert result.taxprofiler.fastp.total_reads_before_filtering == 1000000
        assert result.taxprofiler.classifiers["kraken2"].classified_reads == 950000

    def test_flat_sample_fields_validate(self):
        doc = minimal_sample_doc(sample_id="SRR001", sample_source="csf")
        result = SampleResponse.model_validate(doc)
        assert result.sample_id == "SRR001"
        assert result.sample_source == "csf"

    def test_model_dump_json_serialises_datetime(self):
        doc = minimal_sample_doc(ingested_at=datetime(2024, 3, 15, 10, 0, 0))
        dump = SampleResponse.model_validate(doc).model_dump(mode="json")
        assert isinstance(dump["ingested_at"], str)

    def test_unknown_classifier_qc_fields_ignored(self):
        doc = minimal_sample_doc(
            taxprofiler={
                "classifiers": {
                    "kraken2": {"pct_unclassified": 5.0, "pct_top_one": 99.0}
                }
            }
        )
        result = SampleResponse.model_validate(doc)
        assert result.taxprofiler.classifiers["kraken2"].pct_unclassified == 5.0


class TestCaseResponse:
    def test_minimal_valid_document(self):
        assert CaseResponse.model_validate(minimal_case_doc()).case_id == "speedysnake"

    def test_extra_fields_allowed(self):
        CaseResponse.model_validate(minimal_case_doc(future_field="value"))

    def test_defaults_applied(self):
        result = CaseResponse.model_validate(minimal_case_doc())
        assert result.has_krona is False
        assert result.classifiers == []
        assert result.notes == []
        assert result.review.reviewed is False

    def test_classifiers_validated(self):
        doc = minimal_case_doc(
            classifiers=[{"name": "kraken2", "db": "k2_pluspf", "krona_id": "abc"}]
        )
        result = CaseResponse.model_validate(doc)
        assert result.classifiers[0].name == "kraken2"

    def test_classifier_missing_krona_id_defaults_none(self):
        doc = minimal_case_doc(classifiers=[{"name": "kraken2", "db": "k2_pluspf"}])
        assert CaseResponse.model_validate(doc).classifiers[0].krona_id is None

    def test_notes_validated(self):
        doc = minimal_case_doc(
            notes=[
                {
                    "id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "text": "Looks clean",
                    "author": "admin",
                    "created_at": "2024-03-15T10:00:00",
                }
            ]
        )
        result = CaseResponse.model_validate(doc)
        assert result.notes[0].author == "admin"

    def test_pipeline_info_nested_config_validates(self):
        doc = minimal_case_doc(
            pipeline_info={
                "software_used": {},
                "pipeline_configuration": {
                    "pipeline_name": "nf-core/taxprofiler",
                    "pipeline_version": "1.1.3",
                    "nextflow": "23.10.1",
                },
            }
        )
        cfg = CaseResponse.model_validate(doc).pipeline_info.pipeline_configuration
        assert cfg.pipeline_name == "nf-core/taxprofiler"
        assert cfg.nextflow == "23.10.1"

    def test_review_status_validated(self):
        doc = minimal_case_doc(review={"reviewed": True, "reviewed_by": "alice"})
        assert CaseResponse.model_validate(doc).review.reviewed_by == "alice"

    def test_model_dump_json_mode(self):
        dump = CaseResponse.model_validate(minimal_case_doc()).model_dump(mode="json")
        assert dump["case_id"] == "speedysnake"


class TestClassifierQcStats:
    def test_all_fields_optional(self):
        stats = ClassifierQcStats()
        assert stats.pct_unclassified is None
        assert stats.classified_reads is None

    def test_values_set_correctly(self):
        stats = ClassifierQcStats(
            pct_unclassified=5.0, classified_reads=950000, num_species=42
        )
        assert stats.num_species == 42

    def test_old_fields_ignored(self):
        stats = ClassifierQcStats.model_validate(
            {"pct_unclassified": 5.0, "pct_top_one": 99.0}
        )
        assert stats.pct_unclassified == 5.0


class TestTaxonEntry:
    def test_valid_entry(self):
        entry = TaxonEntry(taxon_id=1279, name="Staphylococcus", abundance=500.0)
        assert entry.superkingdom is None

    def test_rank_optional(self):
        assert TaxonEntry(taxon_id=1, name="root", abundance=1000.0).rank is None


class TestClassifierProfile:
    def test_profile_list_validated(self):
        profile = ClassifierProfile(
            classifier="kraken2",
            classifier_db="k2_pluspf",
            profile=[{"taxon_id": 9606, "name": "Homo sapiens", "abundance": 300.0}],
        )
        assert profile.profile[0].taxon_id == 9606


class TestPipelineConfiguration:
    def test_all_fields_optional(self):
        cfg = PipelineConfiguration()
        assert cfg.pipeline_name is None

    def test_fields_set(self):
        cfg = PipelineConfiguration(
            pipeline_name="nf-core/taxprofiler",
            pipeline_version="1.1.3",
            nextflow="23.10.1",
        )
        assert cfg.pipeline_name == "nf-core/taxprofiler"


class TestReviewStatus:
    def test_defaults(self):
        r = ReviewStatus()
        assert r.reviewed is False
        assert r.reviewed_by is None

    def test_unknown_fields_ignored(self):
        r = ReviewStatus.model_validate({"reviewed": True, "extra": "ignored"})
        assert r.reviewed is True
