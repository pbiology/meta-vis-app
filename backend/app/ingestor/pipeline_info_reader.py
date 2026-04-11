# app/ingestor/pipeline_info_reader.py

import yaml
from pathlib import Path

from app.ingestor.models import PipelineConfiguration, PipelineInfoOutput


def read_pipeline_info(pipeline_info_path: str) -> PipelineInfoOutput:
    path = Path(pipeline_info_path)

    if not path.exists():
        raise FileNotFoundError(f"Pipeline info file not found: {pipeline_info_path}")

    if not path.is_file():
        raise ValueError(
            f"Expected a file, got a directory: {pipeline_info_path}. Pass the yml file directly."
        )

    with open(path) as f:
        data: dict = yaml.safe_load(f) or {}

    if "Workflow" not in data:
        raise ValueError(
            f"'{pipeline_info_path}' does not appear to be a valid pipeline software versions file — "
            f"missing 'Workflow' key."
        )

    workflow_info = data.pop("Workflow", {})

    nextflow_version: str | None = workflow_info.get("Nextflow")
    pipeline_version: str | None = next(
        (v for k, v in workflow_info.items() if k != "Nextflow"), None
    )
    pipeline_name: str | None = next(
        (k for k in workflow_info.keys() if k != "Nextflow"), None
    )

    return PipelineInfoOutput(
        software_used=data,
        pipeline_configuration=PipelineConfiguration(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            nextflow=nextflow_version,
        ),
    )
