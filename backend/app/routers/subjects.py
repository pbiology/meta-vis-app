# app/routers/subjects.py

import re
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user
from app.case_access import ANALYSIS_SUMMARY_PROJECTION, serialise_case
from app.database import get_db
from app.models.case import CaseListItem
from app.models.subject import Subject, SubjectListItem, SubjectsResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])

PAGE_SIZE = 50


def _try_parse_oid(value: str) -> ObjectId | None:
    """Return an ObjectId if `value` is a valid 24-char hex string, else None."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def _analysis_counts_by_subject(
    db: AsyncIOMotorDatabase, subject_oids: list[ObjectId]
) -> dict[ObjectId, dict[str, int]]:
    """Count a subject's cases, split by the analysis_type of their latest run.

    Returns ``{subject_oid: {analysis_type: count}}``. ``analysis_type`` lives
    on the analysis rather than the case — a re-sequencing can legitimately
    switch platform or assay — so this walks cases to analyses in two steps
    rather than one ``$group``. Counting only latest analyses keeps a
    re-sequenced case counted once.
    """
    if not subject_oids:
        return {}

    subject_by_case: dict[str, ObjectId] = {
        doc["case_id"]: doc["subject_id"]
        async for doc in db["cases"].find(
            {"subject_id": {"$in": subject_oids}}, {"case_id": 1, "subject_id": 1}
        )
    }
    if not subject_by_case:
        return {}

    counts: dict[ObjectId, dict[str, int]] = {}
    async for doc in db["case_analysis"].find(
        {"case_id": {"$in": list(subject_by_case)}, "is_latest": True},
        {"case_id": 1, "analysis_type": 1},
    ):
        subject_oid = subject_by_case[doc["case_id"]]
        analysis_type = doc.get("analysis_type")
        bucket = counts.setdefault(subject_oid, {})
        bucket[analysis_type] = bucket.get(analysis_type, 0) + 1
    return counts


@router.get("", summary="List subjects with per-subject analysis counts")
async def list_subjects(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _user: Annotated[dict, Depends(get_current_user)],
    page: int = 1,
    search: Annotated[str, Query(max_length=128)] = "",
) -> SubjectsResponse:
    query: dict[str, object] = {}
    if search.strip():
        query["subject_id"] = {"$regex": re.escape(search.strip()), "$options": "i"}

    total = await db["subjects"].count_documents(query)
    skip = (page - 1) * PAGE_SIZE

    docs = (
        await db["subjects"]
        .find(query)
        .sort("subject_id", 1)
        .skip(skip)
        .limit(PAGE_SIZE)
        .to_list(length=PAGE_SIZE)
    )

    counts = await _analysis_counts_by_subject(db, [d["_id"] for d in docs])

    items = [
        SubjectListItem(
            subject_id=doc["subject_id"],
            sex=doc.get("sex", "unknown"),
            shotgun_count=counts.get(doc["_id"], {}).get("shotgun", 0),
            amplicon_count=counts.get(doc["_id"], {}).get("amplicon", 0),
        )
        for doc in docs
    ]

    return SubjectsResponse(
        total=total,
        page=page,
        pages=max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        items=items,
    )


async def _resolve_subject_oid(
    db: AsyncIOMotorDatabase, subject_id: str
) -> ObjectId | None:
    """Resolve a subject (by ObjectId hex or human subject_id) to its ``_id``.

    The ``_id`` is the durable FK stored on cases/samples, so callers need it to
    query related documents. Mirrors the dual-lookup logic of ``get_subject``.
    """
    oid = _try_parse_oid(subject_id)
    if oid is not None:
        doc = await db["subjects"].find_one({"_id": oid}, {"_id": 1})
        if doc:
            return doc["_id"]
    doc = await db["subjects"].find_one({"subject_id": subject_id}, {"_id": 1})
    return doc["_id"] if doc else None


@router.get(
    "/{subject_id}/cases",
    summary="List cases for a subject",
    responses={404: {"description": "Subject not found"}},
)
async def list_subject_cases(
    subject_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _user: Annotated[dict, Depends(get_current_user)],
) -> list[CaseListItem]:
    oid = await _resolve_subject_oid(db, subject_id)
    if oid is None:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    # One row per clinical case, showing its latest analysis — the same shape
    # the Cases list renders, so a re-sequenced case appears once here too.
    # Sorting happens on the analyses because that is where the sort keys live.
    cases_by_id = {
        doc["case_id"]: doc async for doc in db["cases"].find({"subject_id": oid})
    }
    if not cases_by_id:
        return []

    latest_docs = (
        await db["case_analysis"]
        .find(
            {"case_id": {"$in": list(cases_by_id)}, "is_latest": True},
            ANALYSIS_SUMMARY_PROJECTION,
        )
        .sort([("review.reviewed", 1), ("order_date", -1), ("ingested_at", -1)])
        .to_list(length=None)
    )

    superseded_by_case: dict[str, list[dict]] = {}
    async for doc in (
        db["case_analysis"]
        .find(
            {"case_id": {"$in": list(cases_by_id)}, "is_latest": False},
            ANALYSIS_SUMMARY_PROJECTION,
        )
        .sort("version", -1)
    ):
        superseded_by_case.setdefault(doc["case_id"], []).append(doc)

    return [
        CaseListItem.model_validate(
            {
                "case": serialise_case(cases_by_id[latest["case_id"]]),
                "latest": latest,
                "superseded_analyses": superseded_by_case.get(latest["case_id"], []),
            }
        )
        for latest in latest_docs
    ]


@router.get("/{subject_id}", summary="Get a subject by id")
async def get_subject(
    subject_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> Subject:
    # Accept either the human subject_id (e.g. "26CE100005") or the Mongo
    # ObjectId hex (used as the durable FK on cases/samples). When the path
    # parses as an ObjectId, try _id first so the common report path is a
    # single round-trip; fall back to subject_id so legacy callers keep
    # working.
    oid = _try_parse_oid(subject_id)
    doc = None
    if oid is not None:
        doc = await db["subjects"].find_one({"_id": oid}, {"_id": 0})
    if doc is None:
        doc = await db["subjects"].find_one({"subject_id": subject_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    return Subject.model_validate(doc)
