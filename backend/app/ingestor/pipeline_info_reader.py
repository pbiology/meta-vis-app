import yaml
from pathlib import Path


def read_pipeline_info(pipeline_info_path: str) -> dict:
    path = Path(pipeline_info_path)

    if not path.exists():
        raise FileNotFoundError(f"Pipeline info file not found: {pipeline_info_path}")

    if not path.is_file():
        raise ValueError(f"Expected a file, got a directory: {pipeline_info_path}. Pass the yml file directly.")

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    if "Workflow" not in data:
        raise ValueError(
            f"'{pipeline_info_path}' does not appear to be a valid pipeline software versions file — "
            f"missing 'Workflow' key."
        )

    workflow_info = data.pop("Workflow", {})

    # Normalise key capitalisation — older files use 'nf-core/taxprofiler', newer use it too
    pipeline_version = workflow_info.get("nf-core/taxprofiler")
    nextflow_version = workflow_info.get("Nextflow")

    return {
        "software_used": data,
        "pipeline_configuration": {
            "pipeline": pipeline_version,
            "nextflow": nextflow_version,
        },
    }