# app/routers/subjects.py

import re
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user
from app.database import get_db
from app.models.case import CaseResponse
from app.models.subject import Subject, SubjectListItem, SubjectsResponse
from app.routers.cases import _serialise_case

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
    """Count cases per subject, split by analysis_type.

    Returns ``{subject_oid: {analysis_type: count}}`` for the given subjects.
    One case == one pipeline run / analysis. Done as a single ``$group`` over
    ``cases`` (well supported by mongomock-motor) rather than a ``$lookup`` on
    the subjects pipeline, keeping the data flow easy to follow.
    """
    if not subject_oids:
        return {}
    pipeline: list[dict] = [
        {"$match": {"subject_id": {"$in": subject_oids}}},
        {
            "$group": {
                "_id": {"subject_id": "$subject_id", "type": "$analysis_type"},
                "count": {"$sum": 1},
            }
        },
    ]
    counts: dict[ObjectId, dict[str, int]] = {}
    async for row in db["cases"].aggregate(pipeline):
        subject_oid = row["_id"]["subject_id"]
        analysis_type = row["_id"]["type"]
        counts.setdefault(subject_oid, {})[analysis_type] = row["count"]
    return counts


@router.get("", summary="List subjects with per-subject analysis counts")
async def list_subjects(
    page: int = 1,
    search: Annotated[str, Query(max_length=128)] = "",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
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


@router.get("/{subject_id}/cases", summary="List cases for a subject")
async def list_subject_cases(
    subject_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[CaseResponse]:
    oid = await _resolve_subject_oid(db, subject_id)
    if oid is None:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    # Same sort and per-row defaults as cases.list_cases so the rows render
    # identically to the Cases list; _serialise_case/CaseResponse are reused to
    # avoid duplicating the case serialisation contract.
    docs = (
        await db["cases"]
        .find({"subject_id": oid})
        .sort([("review.reviewed", 1), ("order_date", -1), ("ingested_at", -1)])
        .to_list(length=None)
    )

    result = []
    for doc in docs:
        doc.setdefault("sample_count", 0)
        doc.setdefault("control_count", 0)
        doc.setdefault("sample_names", [])
        result.append(CaseResponse.model_validate(_serialise_case(doc)))
    return result


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
