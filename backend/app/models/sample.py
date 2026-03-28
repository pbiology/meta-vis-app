from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# --- Taxonomic profile ---

class TaxonEntry(BaseModel):
    taxon_id: int
    name: str
    rank: Optional[str] = None
    abundance: float


class ClassifierProfile(BaseModel):
    classifier: Literal["kraken2", "bracken", "metaphlan", "kaiju", "diamond"]
    classifier_db: Optional[str] = None
    profile: list[TaxonEntry] = []


# --- QC / pipeline stats ---

class FastQCStats(BaseModel):
    total_sequences: Optional[float] = None
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


class PipelineConfig(BaseModel):
    pipeline: Optional[str] = None
    nextflow: Optional[str] = None


class PipelineInfo(BaseModel):
    software_used: dict[str, dict] = {}
    pipeline_configuration: Optional[PipelineConfig] = None


class TaxprofilerStats(BaseModel):
    fastqc: Optional[FastQCStats] = None
    fastp: Optional[FastpStats] = None
    kraken2: Optional[Kraken2Stats] = None
    bowtie2: Optional[Bowtie2Stats] = None
    pipeline_info: Optional[PipelineInfo] = None


# --- Clinical / sample metadata ---

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


# --- Top-level sample document ---

class SampleDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    run_id: str
    patient_id: str
    sample_type: Literal["test", "negative_ctrl", "positive_ctrl"]
    sample: SampleMetadata
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    profiles: list[ClassifierProfile] = []
    krona_path: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


# --- Ingest request ---

class SampleIngestRequest(BaseModel):
    patient_id: str
    sample_type: Literal["test", "negative_ctrl", "positive_ctrl"]
    taxpasta_path: str
    taxpasta_column: str
    classifier: Literal["kraken2", "bracken", "metaphlan", "kaiju", "diamond"] = "kraken2"
    classifier_db: Optional[str] = None
    multiqc_path: str
    pipeline_info_path: str
    krona_path: Optional[str] = None
    sample: SampleMetadata
    library_preparation: Optional[LibraryPreparation] = None
    sequencing: Optional[SequencingMetadata] = None


class IngestRequest(BaseModel):
    run_id: str
    samples: list[SampleIngestRequest]

    model_config = {
        "json_schema_extra": {
            "example": {
                "run_id": "run_2024_03_28",
                "samples": [
                    {
                        "patient_id": "P001",
                        "sample_type": "test",
                        "taxpasta_path": "/data/taxprofiler/results/taxpasta/kraken2_k2_pluspf.tsv",
                        "taxpasta_column": "PE-04-28_k2_pluspf.kraken2.kraken2.report",
                        "classifier": "kraken2",
                        "classifier_db": "k2_pluspf",
                        "multiqc_path": "/data/taxprofiler/results/multiqc/multiqc_data.json",
                        "pipeline_info_path": "/data/taxprofiler/results/pipeline_info",
                        "krona_path": "/data/taxprofiler/results/krona/PE-04-28.krona.html",
                        "sample": {
                            "sample_id": "PE-04-28",
                            "sample_source": "cerebrospinal_fluid",
                            "biopsy_id": "BB22"
                        }
                    }
                ]
            }
        }
    }