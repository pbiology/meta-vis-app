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
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Full sample document (stored in MongoDB)
# ---------------------------------------------------------------------------

class SampleDocument(BaseModel):
    case_id: ObjectId
    subject_id: Optional[ObjectId] = None   # null for controls
    sample_type: str                         # test | positive_ctrl | negative_ctrl
    material: str                            # DNA | RNA
    order_date: Optional[date] = None
    sample: SampleMetadata
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    profiles: List[ClassifierProfile] = []
    has_krona: bool = False                  # krona stored at case level
    review: ReviewStatus = ReviewStatus()
    ingested_at: datetime

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Ingest request models
# ---------------------------------------------------------------------------

class MetavalIngestRequest(BaseModel):
    igv_dir: str   # path to the metaval igv/ directory

class ClassifierIngestRequest(BaseModel):
    name: str                    # e.g. "kraken2" or "centrifuge"
    db: str                      # e.g. "k2_pluspf" or "p_compressed+h+v"
    taxpasta: str                # path to taxpasta TSV
    krona: Optional[str] = None  # path to krona HTML


class SampleIngestRequest(BaseModel):
    subject_id: Optional[str] = None
    sample_id: str
    sample_type: str = "test"
    material: str = "DNA"
    order_date: Optional[date] = None
    columns: dict                # {"kraken2": "PE-04-28_k2_pluspf...", "centrifuge": "PE-04-28_p_compressed+h+v.centrifuge"}
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None


class IngestRequest(BaseModel):
    case_id: str
    multiqc_path: str
    pipeline_info_path: str
    classifiers: List[ClassifierIngestRequest]
    samples: List[SampleIngestRequest]
    metaval: Optional[MetavalIngestRequest] = None