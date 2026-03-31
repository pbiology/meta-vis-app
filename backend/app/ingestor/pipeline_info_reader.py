import yaml
from pathlib import Path


def read_pipeline_info(pipeline_info_path: str) -> dict:
    path = Path(pipeline_info_path)

    if not path.exists():
        raise FileNotFoundError(f"Pipeline info file not found: {pipeline_info_path}")

    if path.is_dir():
        # Legacy: accept a directory and find the file within it
        versions_file = next(path.glob("nf_core_*_software_mqc_versions.yml"), None)
        if not versions_file:
            raise FileNotFoundError(
                f"No software versions file found in {pipeline_info_path}. "
                f"Expected a file matching 'nf_core_*_software_mqc_versions.yml'."
            )
    else:
        versions_file = path

    with open(versions_file) as f:
        software_versions = yaml.safe_load(f) or {}

    workflow_info = software_versions.pop("Workflow", {})

    return {
        "software_used": software_versions,
        "pipeline_configuration": {
            "pipeline": workflow_info.get("nf-core/taxprofiler"),
            "nextflow": workflow_info.get("Nextflow"),
        },
    }