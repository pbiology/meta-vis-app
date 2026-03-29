# app/models/sample.py

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from bson import ObjectId


# ---------------------------------------------------------------------------
# Taxonomic profile
# ---------------------------------------------------------------------------

class TaxonEntry(BaseModel):
    taxon_id: int
    name: str
    rank: Optional[str] = None
    abundance: float
    superkingdom: Optional[str] = None  # Bacteria | Archaea | Eukaryota | Viruses


class ClassifierProfile(BaseModel):
    classifier: str
    classifier_db: str
    profile: List[TaxonEntry]


# ---------------------------------------------------------------------------
# QC blocks
# ---------------------------------------------------------------------------

class FastQCStats(BaseModel):
    total_sequences: Optional[int] = None
    avg_sequence_length: Optional[float] = None
    pct_gc_forward: Optional[float] = None
    pct_gc_reverse: Optional[float] = None
    pct_poor_quality_forward: Optional[float] = None
    pct_poor_quality_reverse: Optional[float] = None


class FastpStats(BaseModel):
    total_reads_before_filtering: Optional[int] = None
    total_reads_after_filtering: Optional[int] = None
    passed_filter_reads: Optional[int] = None
    low_quality_reads: Optional[int] = None
    too_short_reads: Optional[int] = None
    q20_rate: Optional[float] = None
    q30_rate: Optional[float] = None
    gc_content: Optional[float] = None


class Kraken2Stats(BaseModel):
    pct_unclassified: Optional[float] = None
    pct_top_one: Optional[float] = None
    pct_top_n: Optional[float] = None
    unclassified_reads: Optional[int] = None
    num_species: Optional[int] = None
    num_genera: Optional[int] = None


class Bowtie2Stats(BaseModel):
    total_reads: Optional[int] = None
    aligned_exactly_one: Optional[int] = None
    aligned_multi: Optional[int] = None
    aligned_none: Optional[int] = None
    overall_alignment_rate: Optional[float] = None


class PipelineInfo(BaseModel):
    software_used: Optional[dict] = None
    pipeline_configuration: Optional[dict] = None


class TaxprofilerStats(BaseModel):
    kraken2: Optional[Kraken2Stats] = None
    fastqc: Optional[FastQCStats] = None
    fastp: Optional[FastpStats] = None
    bowtie2: Optional[Bowtie2Stats] = None
    pipeline_info: Optional[PipelineInfo] = None


# ---------------------------------------------------------------------------
# Sample metadata
# ---------------------------------------------------------------------------

class SampleMetadata(BaseModel):
    sample_id: str
    sample_source: Optional[str] = None
    biopsy_id: Optional[str] = None


class LibraryPreparation(BaseModel):
    library_name: Optional[str] = None
    batch_id: Optional[str] = None
    sample_type: Optional[str] = None


class SequencingMetadata(BaseModel):
    platform: Optional[str] = None
    flowcell_id: Optional[str] = None
    date: Optional[str] = None
    barcode_index: Optional[str] = None
    num_reads: Optional[int] = None


# ---------------------------------------------------------------------------
# Review subdocument
# ---------------------------------------------------------------------------

class ReviewStatus(BaseModel):
    reviewed: bool = False
    reviewed_by: Optional[str] = None   # username
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Full sample document (stored in MongoDB)
# ---------------------------------------------------------------------------

class SampleDocument(BaseModel):
    run_id: ObjectId
    subject_id: ObjectId
    sample_type: str                        # test | negative_ctrl | positive_ctrl
    order_date: Optional[date] = None       # when sample was submitted for sequencing
    sample: SampleMetadata
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    profiles: List[ClassifierProfile] = []
    krona_path: Optional[str] = None
    review: ReviewStatus = ReviewStatus()
    ingested_at: datetime

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Ingest request models
# ---------------------------------------------------------------------------

class SampleIngestRequest(BaseModel):
    subject_id: str
    sample_type: str = "test"               # test | negative_ctrl | positive_ctrl
    order_date: Optional[date] = None       # ISO date e.g. "2026-03-01"
    taxpasta_path: str
    taxpasta_column: str
    classifier: str
    classifier_db: str
    multiqc_path: str
    pipeline_info_path: str
    nodes_data: Optional[str] = None        # absolute path to NCBI taxonomy nodes.dmp
    krona_path: Optional[str] = None
    sample: SampleMetadata
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None


class IngestRequest(BaseModel):
    run_id: str
    samples: List[SampleIngestRequest]