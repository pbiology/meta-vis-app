# app/models/ingest.py
"""Ingest manifest models — the wire contract between the ingest CLI and the
backend. The CLI uploads a tar.gz bundle whose manifest.json deserialises into
one of the *IngestMeta models below. File paths are NOT part of the wire
model — everything is addressed by arcname inside the bundle
(see app.ingestor.loader)."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.common import AnalysisType, SequencingPlatform


# ---------------------------------------------------------------------------
# Shared sample-entry rules
# ---------------------------------------------------------------------------


def _assert_order_date_is_control_only(
    sample_id: str, sample_type: str, order_date: Optional[date]
) -> None:
    """Reject a per-sample order date on a clinical sample.

    A control is prepared once and sequenced alongside every case in its run, so
    its order date belongs to the control. A clinical sample is ordered as part
    of its case, so a date of its own could only disagree with the case's — the
    drift this field exists to remove, not to introduce.
    """
    if sample_type == "sample" and order_date is not None:
        raise ValueError(
            f"Sample '{sample_id}' has sample_type='sample' and must not set "
            "order_date: a clinical sample is ordered as part of its case and "
            "takes the case's order date. Only controls carry their own."
        )


# ---------------------------------------------------------------------------
# Taxprofiler ingest manifest
# ---------------------------------------------------------------------------


class TaxprofilerClassifierMeta(BaseModel):
    """One classifier within a taxprofiler ingest manifest."""

    name: str  # e.g. "kraken2" or "centrifuge"
    db: str  # e.g. "k2_pluspf" or "p_compressed+h+v"


class TaxprofilerSampleIngestRequest(BaseModel):
    # subject_id is required for clinical samples but not for controls (NTC /
    # positive control) — controls have no clinical subject. The validator
    # below enforces this. subject_sex is only persisted when a subject_id is
    # present.
    subject_id: Optional[str] = None
    subject_sex: Literal["F", "M", "X", "unknown"] = "unknown"
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    nucleic_acid: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    # A control is prepared once and sequenced alongside every case in its run,
    # so its order date is a property of the control, not of any one case. Left
    # unset, the sample inherits the case's order date — always right for a
    # clinical sample, which is why the validator below rejects it there.
    order_date: Optional[date] = None
    # classifier_name -> taxpasta column name
    columns: dict

    @model_validator(mode="after")
    def _require_subject_for_clinical_samples(self):
        if self.sample_type == "sample" and not self.subject_id:
            raise ValueError(
                f"Sample '{self.sample_id}' has sample_type='sample' and must "
                "provide a subject_id."
            )
        return self

    @model_validator(mode="after")
    def _reject_order_date_on_clinical_samples(self):
        _assert_order_date_is_control_only(
            self.sample_id, self.sample_type, self.order_date
        )
        return self


class TaxprofilerIngestMeta(BaseModel):
    """Taxprofiler ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    classifiers: List[TaxprofilerClassifierMeta]
    samples: List[TaxprofilerSampleIngestRequest]
    # True iff the bundle includes a metaval/ subtree.
    has_metaval: bool = False
    # True iff classifiers/<name>/krona/<file> is present for the named classifier.
    classifiers_with_krona: List[str] = Field(default_factory=list)
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None


# ---------------------------------------------------------------------------
# Trana ingest manifest
# ---------------------------------------------------------------------------


class TranaSampleIngestRequest(BaseModel):
    """Per-sample input for Trana pipeline ingest. Files live in the bundle
    under samples/<sample_id>/ (abundance.tsv, optional krona.html,
    optional nanoplot_unprocessed/NanoStats.txt, optional
    nanoplot_processed/NanoStats.txt)."""

    # See TaxprofilerSampleIngestRequest for the subject_id / sample_type and
    # order_date rules.
    subject_id: Optional[str] = None
    subject_sex: Literal["F", "M", "X", "unknown"] = "unknown"
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    nucleic_acid: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    order_date: Optional[date] = None
    has_krona: bool = False
    has_nanoplot_unprocessed: bool = False
    has_nanoplot_processed: bool = False

    @model_validator(mode="after")
    def _require_subject_for_clinical_samples(self):
        if self.sample_type == "sample" and not self.subject_id:
            raise ValueError(
                f"Sample '{self.sample_id}' has sample_type='sample' and must "
                "provide a subject_id."
            )
        return self

    @model_validator(mode="after")
    def _reject_order_date_on_clinical_samples(self):
        _assert_order_date_is_control_only(
            self.sample_id, self.sample_type, self.order_date
        )
        return self


class TranaIngestMeta(BaseModel):
    """Trana ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    samples: List[TranaSampleIngestRequest]
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
