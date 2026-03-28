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