# tests/unit/test_pipeline_info_reader.py

import pytest
import yaml
from app.ingestor.pipeline_info_reader import read_pipeline_info


def write_yaml(tmp_path, data: dict, filename: str = "versions.yml"):
    p = tmp_path / filename
    p.write_text(yaml.dump(data))
    return str(p)


VALID_PIPELINE_INFO = {
    "Workflow": {
        "nf-core/taxprofiler": "1.2.0",
        "Nextflow": "24.04.0",
    },
    "Kraken2": {
        "kraken2": "2.1.3",
    },
    "Fastp": {
        "fastp": "0.23.4",
    },
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_read_pipeline_info_returns_model(tmp_path):
    path = write_yaml(tmp_path, VALID_PIPELINE_INFO)
    result = read_pipeline_info(path)
    from app.models.pipeline import PipelineInfo

    assert isinstance(result, PipelineInfo)


def test_pipeline_configuration_extracted(tmp_path):
    path = write_yaml(tmp_path, VALID_PIPELINE_INFO)
    result = read_pipeline_info(path)
    config = result.pipeline_configuration
    assert config.pipeline_name == "nf-core/taxprofiler"
    assert config.pipeline_version == "1.2.0"
    assert config.nextflow == "24.04.0"


def test_software_used_excludes_workflow(tmp_path):
    path = write_yaml(tmp_path, VALID_PIPELINE_INFO)
    result = read_pipeline_info(path)
    assert "Workflow" not in result.software_used
    assert "Kraken2" in result.software_used
    assert "Fastp" in result.software_used


def test_nextflow_version_correct(tmp_path):
    path = write_yaml(tmp_path, VALID_PIPELINE_INFO)
    result = read_pipeline_info(path)
    assert result.pipeline_configuration.nextflow == "24.04.0"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        read_pipeline_info("/nonexistent/versions.yml")


def test_directory_path_raises(tmp_path):
    with pytest.raises(ValueError, match="Expected a file"):
        read_pipeline_info(str(tmp_path))


def test_missing_workflow_key_raises(tmp_path):
    path = write_yaml(tmp_path, {"Kraken2": {"kraken2": "2.1.3"}})
    with pytest.raises(ValueError, match="missing 'Workflow' key"):
        read_pipeline_info(path)
