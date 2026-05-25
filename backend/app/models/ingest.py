# app/models/ingest.py
"""Ingest manifest models — the wire contract between the ingest CLI and the
backend. The CLI uploads a tar.gz bundle whose manifest.json deserialises into
one of the *IngestMeta models below. File paths are NOT part of the wire
model — everything is addressed by arcname inside the bundle
(see app.ingestor.loader)."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.common import AnalysisType, SequencingPlatform


# ---------------------------------------------------------------------------
# Taxprofiler ingest manifest
# ---------------------------------------------------------------------------


class TaxprofilerClassifierMeta(BaseModel):
    """One classifier within a taxprofiler ingest manifest."""

    name: str  # e.g. "kraken2" or "centrifuge"
    db: str  # e.g. "k2_pluspf" or "p_compressed+h+v"


class TaxprofilerSampleIngestRequest(BaseModel):
    subject_id: Optional[str] = None
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    # classifier_name -> taxpasta column name
    columns: dict


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

    subject_id: Optional[str] = None
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    has_krona: bool = False
    has_nanoplot_unprocessed: bool = False
    has_nanoplot_processed: bool = False


class TranaIngestMeta(BaseModel):
    """Trana ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    samples: List[TranaSampleIngestRequest]
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
