# app/models/subject.py

from typing import List, Literal

from pydantic import BaseModel, ConfigDict


class Subject(BaseModel):
    """A research/clinical subject linked to one or more samples.

    Stored in the ``subjects`` collection (see ``database.py::_ensure_indexes``,
    where ``subject_id`` carries a unique index). The ingest orchestrator upserts
    subject documents from the ingest payload via ``_resolve_subject_ids``.
    """

    subject_id: str
    sex: Literal["F", "M", "X", "unknown"] = "unknown"

    # extra="allow" keeps room for future fields (birth_year, ward, …) without a
    # model bump — mirrors the posture of SampleResponse.
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SubjectListItem(BaseModel):
    """One row in the subjects list, with per-subject analysis counts.

    ``shotgun_count`` / ``amplicon_count`` are the number of the subject's cases
    (one case == one pipeline run / analysis) of each ``analysis_type``,
    computed by the list endpoint from the ``cases`` collection.
    """

    subject_id: str
    sex: Literal["F", "M", "X", "unknown"] = "unknown"
    shotgun_count: int = 0
    amplicon_count: int = 0


class SubjectsResponse(BaseModel):
    """Paginated subjects list — mirrors the shape of the cases list."""

    total: int
    page: int
    pages: int
    items: List[SubjectListItem] = []
