# app/models/sample.py

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, ConfigDict

from app.ingestor.models import (
    TaxonEntry as TaxonEntry,
    PipelineConfiguration as PipelineConfiguration,
    PipelineInfoOutput as PipelineInfo,  # re-exported under the existing name used by the API layer
)


class AnalysisType(str, Enum):
    SHOTGUN = "shotgun"
    AMPLICON = "amplicon"


class SequencingPlatform(str, Enum):
    ILLUMINA = "illumina"
    NANOPORE = "nanopore"


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------
# Taxonomic profile
# ---------------------------------------------------------------------------


class ClassifierProfile(BaseModel):
    classifier: str
    classifier_db: str
    profile: List[TaxonEntry]


# ---------------------------------------------------------------------------
# QC blocks
# ---------------------------------------------------------------------------


class FastQCStats(_Base):
    total_sequences: Optional[int] = None
    avg_sequence_length: Optional[float] = None
    pct_gc_forward: Optional[float] = None
    pct_gc_reverse: Optional[float] = None
    pct_poor_quality_forward: Optional[float] = None
    pct_poor_quality_reverse: Optional[float] = None


class FastpStats(_Base):
    total_reads_before_filtering: Optional[int] = None
    total_reads_after_filtering: Optional[int] = None
    passed_filter_reads: Optional[int] = None
    low_quality_reads: Optional[int] = None
    too_short_reads: Optional[int] = None
    q20_rate: Optional[float] = None
    q30_rate: Optional[float] = None
    gc_content: Optional[float] = None


class ClassifierQcStats(_Base):
    pct_unclassified: Optional[float] = None
    unclassified_reads: Optional[int] = None
    classified_reads: Optional[int] = None
    total_reads: Optional[int] = None
    num_species: Optional[int] = None
    num_genera: Optional[int] = None


class Bowtie2Stats(_Base):
    total_reads: Optional[int] = None
    aligned_exactly_one: Optional[int] = None
    aligned_multi: Optional[int] = None
    aligned_none: Optional[int] = None
    overall_alignment_rate: Optional[float] = None


class TaxprofilerStats(_Base):
    fastp: Optional[FastpStats] = None
    fastqc: Optional[FastQCStats] = None
    bowtie2: Optional[Bowtie2Stats] = None
    classifiers: Optional[Dict[str, ClassifierQcStats]] = None
    pipeline_info: Optional[PipelineInfo] = None


# ---------------------------------------------------------------------------
# Sample metadata
# ---------------------------------------------------------------------------


class SampleMetadata(_Base):
    sample_id: str
    sample_source: Optional[str] = None
    material: Optional[str] = None
    sample_type: Optional[str] = None
    subject_id: Optional[str] = None
    biopsy_id: Optional[str] = None


class LibraryPreparation(_Base):
    library_name: Optional[str] = None
    batch_id: Optional[str] = None
    sample_type: Optional[str] = None


class SequencingMetadata(_Base):
    platform: Optional[str] = None
    flowcell_id: Optional[str] = None
    date: Optional[str] = None
    barcode_index: Optional[str] = None
    num_reads: Optional[int] = None


# ---------------------------------------------------------------------------
# Review subdocument
# ---------------------------------------------------------------------------


class ReviewStatus(_Base):
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Full sample document (stored in MongoDB)
# ---------------------------------------------------------------------------


class SampleResponse(_Base):
    """Validated response model for sample documents read from MongoDB."""

    case_id: str
    sample_id: str
    sample_source: Optional[str] = None
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    subject_id: Optional[str] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    profiles: List[ClassifierProfile] = []
    has_krona: bool = False
    review: ReviewStatus = ReviewStatus()
    ingested_at: Optional[datetime] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ---------------------------------------------------------------------------
# Case document (read from MongoDB)
# ---------------------------------------------------------------------------


class CaseClassifier(_Base):
    name: str
    db: str
    krona_id: Optional[str] = None


class CaseNote(_Base):
    text: str
    author: str
    created_at: str


class CaseResponse(_Base):
    """Validated response model for case documents read from MongoDB."""

    case_id: str
    order_date: Optional[str] = None
    ingested_at: Optional[datetime] = None
    classifiers: List[CaseClassifier] = []
    has_krona: bool = False
    pipeline_info: Optional[PipelineInfo] = None
    metaval_pipeline_info: Optional[PipelineInfo] = None
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
    review: ReviewStatus = ReviewStatus()
    notes: List[CaseNote] = []
    sample_ids: List[str] = []

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ---------------------------------------------------------------------------
# Ingest request models
# ---------------------------------------------------------------------------


class MetavalIngestRequest(BaseModel):
    metaval_dir: str  # path to the metaval output root directory


class ClassifierIngestRequest(BaseModel):
    name: str  # e.g. "kraken2" or "centrifuge"
    db: str  # e.g. "k2_pluspf" or "p_compressed+h+v"
    taxpasta: str  # path to taxpasta TSV
    krona: Optional[str] = None  # path to krona HTML


class SampleIngestRequest(BaseModel):
    subject_id: Optional[str] = None
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    columns: dict


class IngestRequest(BaseModel):
    case_id: str
    order_date: Optional[date] = None
    multiqc_path: str
    pipeline_info_path: str
    classifiers: List[ClassifierIngestRequest]
    samples: List[SampleIngestRequest]
    metaval: Optional[MetavalIngestRequest] = None
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
