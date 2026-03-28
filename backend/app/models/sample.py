from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# --- Taxonomic profile ---

class TaxonEntry(BaseModel):
    taxon_id: int
    name: str
    rank: str
    abundance: float


class ClassifierProfile(BaseModel):
    classifier: Literal["kraken2", "bracken", "metaphlan", "kaiju", "diamond"]
    classifier_db: Optional[str] = None
    profile: list[TaxonEntry] = []


# --- QC / pipeline stats ---

class FastQCStats(BaseModel):
    mean_phred_score_forward: Optional[float] = None
    mean_phred_score_reverse: Optional[float] = None
    total_num_reads: Optional[int] = None


class FastpStats(BaseModel):
    num_trimmed_reads: Optional[int] = None


class Kraken2Stats(BaseModel):
    num_otus: Optional[int] = None


class BrackenStats(BaseModel):
    num_otus: Optional[int] = None


class Bowtie2Stats(BaseModel):
    num_human_reads: Optional[int] = None


class SoftwareVersions(BaseModel):
    software: dict[str, str] = {}


class PipelineConfig(BaseModel):
    revision: Optional[str] = None
    runname: Optional[str] = None
    containerengine: Optional[str] = None
    username: Optional[str] = None
    pipeline_repository_git_url: Optional[str] = None
    pipeline_repository_git_commit: Optional[str] = None


class PipelineInfo(BaseModel):
    software_used: dict[str, SoftwareVersions] = {}
    pipeline_configuration: Optional[PipelineConfig] = None


class TaxprofilerStats(BaseModel):
    fastqc: Optional[FastQCStats] = None
    fastp: Optional[FastpStats] = None
    kraken2: Optional[Kraken2Stats] = None
    bracken: Optional[BrackenStats] = None
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


# --- Ingest request shape ---

class SampleIngestRequest(BaseModel):
    patient_id: str
    sample_type: Literal["test", "negative_ctrl", "positive_ctrl"]
    taxpasta_path: str
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
                        "taxpasta_path": "/data/taxprofiler/AA11/results/taxpasta/AA11.tsv",
                        "multiqc_path": "/data/taxprofiler/AA11/results/multiqc/multiqc_data.json",
                        "pipeline_info_path": "/data/taxprofiler/AA11/results/pipeline_info",
                        "krona_path": "/data/taxprofiler/AA11/results/krona/AA11.krona.html",
                        "sample": {
                            "sample_id": "AA11",
                            "sample_source": "cerebrospinal_fluid",
                            "biopsy_id": "BB22"
                        },
                        "library_preparation": {
                            "library_name": "Nextera XT",
                            "batch_id": "ABC123",
                            "sample_type": "RNA"
                        },
                        "sequencing": {
                            "platform": "Illumina NovaSeq X Plus",
                            "flowcell_id": "AUYASCGC",
                            "date": "2023-01-01",
                            "barcode_index": "ATCG",
                            "num_reads": 100000
                        }
                    }
                ]
            }
        }
    }