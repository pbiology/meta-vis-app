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
    material: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
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

    # See TaxprofilerSampleIngestRequest for the subject_id / sample_type rule.
    subject_id: Optional[str] = None
    subject_sex: Literal["F", "M", "X", "unknown"] = "unknown"
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
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


class TranaIngestMeta(BaseModel):
    """Trana ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    samples: List[TranaSampleIngestRequest]
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
