# app/models/analysis.py
"""Analysis response models — one document per pipeline run, stored in the
``case_analysis`` collection.

A clinical case (``app.models.case``) is sequenced one or more times; each run
produces one ``case_analysis`` document. Exactly one analysis per case carries
``is_latest``, enforced by a partial unique index in ``database.py``.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.models.common import AnalysisType, ReviewStatus, SequencingPlatform, _Base
from app.models.pipeline import PipelineInfo


class CaseClassifier(_Base):
    name: str
    db: str
    krona_id: Optional[str] = None


class AnalysisSummary(_Base):
    """Slim projection of an analysis.

    Backs the version switcher and the superseded rows nested under a case in
    the list. Deliberately omits ``report_selections``, ``sample_names``,
    ``classifiers`` and the pipeline-info blocks — a collapsed row needs none of
    them, and including them would grow the list response with every analysis a
    case accumulates.
    """

    case_id: str
    version: int
    is_latest: bool
    order_date: Optional[str] = None
    ingested_at: Optional[datetime] = None
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
    review: ReviewStatus = ReviewStatus()
    sample_count: int = 0
    control_count: int = 0


class CaseAnalysisResponse(_Base):
    """Validated response model for ``case_analysis`` documents.

    Unlike the case document this model declares every field it carries: the
    counts below used to ride along on ``CaseResponse`` as undeclared extras and
    so bypassed validation entirely.
    """

    case_id: str
    version: int
    is_latest: bool = True
    ingested_at: Optional[datetime] = None
    # Denormalised from the case so the list sort stays index-covered on this
    # collection; a re-sequencing may also carry its own, later order date.
    order_date: Optional[str] = None
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None
    classifiers: List[CaseClassifier] = []
    has_krona: bool = False
    has_multiqc: bool = False
    # Pipeline-info of the producing pipeline — populated for both taxprofiler
    # and trana runs (the PipelineInfo shape itself is pipeline-agnostic).
    pipeline_info: Optional[PipelineInfo] = None
    # Separate slot: metaval runs as an additional step on top of taxprofiler,
    # so its pipeline-info lives alongside the primary one rather than replacing it.
    metaval_pipeline_info: Optional[PipelineInfo] = None
    review: ReviewStatus = ReviewStatus()
    report_selections: dict[str, list[int]] = Field(default_factory=dict)
    sample_count: int = 0
    control_count: int = 0
    sample_names: List[str] = []
