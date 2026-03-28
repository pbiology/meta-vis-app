import json
from pathlib import Path


def read_pipeline_info(pipeline_info_path: str) -> dict:
    path = Path(pipeline_info_path)

    if not path.exists():
        raise FileNotFoundError(f"pipeline_info directory not found: {pipeline_info_path}")

    software_versions = {}
    versions_file = path / "software_versions.yml"
    if versions_file.exists():
        import yaml
        with open(versions_file) as f:
            software_versions = yaml.safe_load(f) or {}

    pipeline_config = {}
    for filename in ["params.json", "nextflow_schema.json"]:
        params_file = path / filename
        if params_file.exists():
            with open(params_file) as f:
                pipeline_config = json.load(f)
            break

    return {
        "software_used": software_versions,
        "pipeline_configuration": pipeline_config,
    }