# app/models/case.py
"""Case response models — one document per pipeline run, stored in the
``cases`` collection (case_id unique index)."""

from datetime import datetime
from typing import List, Optional

from pydantic import ConfigDict, Field

from app.models.common import AnalysisType, ReviewStatus, SequencingPlatform, _Base
from app.models.pipeline import PipelineInfo


class CaseClassifier(_Base):
    name: str
    db: str
    krona_id: Optional[str] = None


class CaseNote(_Base):
    id: str
    text: str
    author: str
    created_at: str


class CaseResponse(_Base):
    """Validated response model for case documents read from MongoDB."""

    case_id: str
    ticket_id: Optional[str] = None
    ticket_url: Optional[str] = None
    order_date: Optional[str] = None
    ingested_at: Optional[datetime] = None
    classifiers: List[CaseClassifier] = []
    has_krona: bool = False
    has_multiqc: bool = False
    # Pipeline-info of the producing pipeline — populated for both taxprofiler
    # and trana cases (the PipelineInfo shape itself is pipeline-agnostic).
    pipeline_info: Optional[PipelineInfo] = None
    # Separate slot: metaval runs as an additional step on top of taxprofiler,
    # so its pipeline-info lives alongside the primary one rather than replacing it.
    metaval_pipeline_info: Optional[PipelineInfo] = None
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
    review: ReviewStatus = ReviewStatus()
    notes: List[CaseNote] = []
    sample_ids: List[str] = []
    # ObjectId of the subject this case belongs to, serialised as str. None
    # for control-only cases (no clinical sample). Enforced one-per-case at
    # ingest by app.ingestor.orchestrator._pick_case_subject.
    subject_id: Optional[str] = None
    report_selections: dict[str, list[int]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow", populate_by_name=True)
