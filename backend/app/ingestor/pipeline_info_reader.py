import yaml
from pathlib import Path


def read_pipeline_info(pipeline_info_path: str) -> dict:
    path = Path(pipeline_info_path)

    if not path.exists():
        raise FileNotFoundError(f"pipeline_info directory not found: {pipeline_info_path}")

    software_versions = {}
    versions_file = next(path.glob("nf_core_*_software_mqc_versions.yml"), None)
    if versions_file:
        with open(versions_file) as f:
            software_versions = yaml.safe_load(f) or {}
    else:
        raise FileNotFoundError(
            f"No software versions file found in {pipeline_info_path}. "
            f"Expected a file matching 'nf_core_*_software_mqc_versions.yml'."
        )

    workflow_info = software_versions.pop("Workflow", {})

    return {
        "software_used": software_versions,
        "pipeline_configuration": {
            "pipeline": workflow_info.get("nf-core/taxprofiler"),
            "nextflow": workflow_info.get("Nextflow"),
        },
    }