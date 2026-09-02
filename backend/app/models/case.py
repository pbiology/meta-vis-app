# app/models/case.py
"""Case response models — one document per clinical case, stored in the
``cases`` collection (case_id unique index).

A case holds only clinical identity: who, which order, which ticket, and the
note thread. Everything a pipeline run produces lives on a ``case_analysis``
document instead — see ``app.models.analysis``. The link is
``case_analysis.case_id``; the case carries no back-reference.
"""

from datetime import datetime
from typing import List, Optional

from app.models.analysis import AnalysisSummary, CaseAnalysisResponse
from app.models.common import _Base


class CaseNote(_Base):
    id: str
    text: str
    author: str
    created_at: str


class CaseResponse(_Base):
    """Clinical identity of a case, independent of how many times it was run.

    Notes live here rather than on the analysis so that a re-sequencing never
    strands the discussion on a superseded run.
    """

    case_id: str
    ticket_id: Optional[str] = None
    # Derived at serialisation from settings.freshdesk_base_url; not stored.
    ticket_url: Optional[str] = None
    order_date: Optional[str] = None
    created_at: Optional[datetime] = None
    # ObjectId of the subject this case belongs to, serialised as str. None
    # for control-only cases (no clinical sample). Enforced one-per-case at
    # ingest by app.ingestor.orchestrator._pick_case_subject.
    subject_id: Optional[str] = None
    notes: List[CaseNote] = []


class CaseDetail(_Base):
    """GET /cases/{case_id} — identity, the analysis being viewed, and a
    summary of every analysis of this case for the version switcher."""

    case: CaseResponse
    analysis: Optional[CaseAnalysisResponse] = None
    analyses: List[AnalysisSummary] = []


class CaseListItem(_Base):
    """One row of GET /cases — a case joined to its latest analysis, with any
    superseded analyses nested beneath it for the expandable group.

    ``latest`` is not optional: the list is driven from the analyses, so a case
    can only appear here by having one.
    """

    case: CaseResponse
    latest: AnalysisSummary
    superseded_analyses: List[AnalysisSummary] = []
