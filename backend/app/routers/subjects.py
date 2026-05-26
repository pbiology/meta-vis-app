# app/routers/subjects.py

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user
from app.database import get_db
from app.models.subject import Subject

router = APIRouter(prefix="/subjects", tags=["subjects"])


def _try_parse_oid(value: str) -> ObjectId | None:
    """Return an ObjectId if `value` is a valid 24-char hex string, else None."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


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
