# app/models/pipeline.py
"""Pipeline-info models — used by both taxprofiler and trana ingest outputs
and surfaced through the API on Case responses."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineConfiguration(_StrictBase):
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[str] = None
    nextflow: Optional[str] = None


class PipelineInfo(_StrictBase):
    """Validated output of pipeline_info_reader.read_pipeline_info()."""

    software_used: dict[str, Any]
    pipeline_configuration: PipelineConfiguration
