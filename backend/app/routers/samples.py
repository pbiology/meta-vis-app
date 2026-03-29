# app/routers/samples.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
import os

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/samples", tags=["samples"])


class ReviewPayload(BaseModel):
    notes: Optional[str] = None


def _oid(sample_id: str) -> ObjectId:
    try:
        return ObjectId(sample_id)
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid sample_id: '{sample_id}'")


def _serialise(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "run_id" in doc:
        doc["run_id"] = str(doc["run_id"])
    if "subject_id" in doc:
        doc["subject_id"] = str(doc["subject_id"])
    return doc


@router.get("/{sample_id}", summary="Get full sample document")
async def get_sample(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["samples"].find_one({"_id": _oid(sample_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return _serialise(doc)


@router.get("/{sample_id}/profile", summary="Get taxonomic profile(s) for a sample")
async def get_profile(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["samples"].find_one(
        {"_id": _oid(sample_id)},
        {"profiles": 1, "sample": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return {
        "sample_id": sample_id,
        "sample": doc.get("sample"),
        "profiles": doc.get("profiles", []),
    }


@router.patch("/{sample_id}/review", summary="Mark a sample as reviewed by the current user")
async def review_sample(
    sample_id: str,
    payload: ReviewPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db["samples"].update_one(
        {"_id": _oid(sample_id)},
        {
            "$set": {
                "review.reviewed": True,
                "review.reviewed_by": current_user["username"],
                "review.reviewed_at": datetime.now(timezone.utc),
                "review.notes": payload.notes,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return {"sample_id": sample_id, "reviewed": True, "reviewed_by": current_user["username"]}


@router.get("/{sample_id}/krona", summary="Serve Krona HTML for a sample")
async def get_krona(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["samples"].find_one({"_id": _oid(sample_id)}, {"krona_path": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    path = doc.get("krona_path")
    if not path:
        raise HTTPException(status_code=404, detail="No Krona file associated with this sample")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Krona file not found on disk: {path}")
    return FileResponse(path, media_type="text/html")