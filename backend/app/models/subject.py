# app/models/subject.py

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class Subject(BaseModel):
    """A research/clinical subject linked to one or more samples.

    Stored in the ``subjects`` collection (see ``database.py::_ensure_indexes``,
    where ``subject_id`` carries a unique index). The ingest orchestrator upserts
    subject documents from the ingest payload via ``_resolve_subject_ids``.
    """

    subject_id: str
    sex: Optional[Literal["F", "M", "X", "unknown"]] = None

    # extra="allow" keeps room for future fields (birth_year, ward, …) without a
    # model bump — mirrors the posture of SampleResponse.
    model_config = ConfigDict(extra="allow", populate_by_name=True)
