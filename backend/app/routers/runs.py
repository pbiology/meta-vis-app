# app/routers/cases.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/cases", tags=["cases"])


class ReviewPayload(BaseModel):
    notes: Optional[str] = None


def _serialise_case(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "sample_ids" in doc:
        doc["sample_ids"] = [str(sid) for sid in doc["sample_ids"]]
    return doc


def _serialise_sample(doc: dict) -> dict:
    doc["_id"]    = str(doc["_id"])
    doc["run_id"] = str(doc["run_id"])
    if doc.get("subject_id"):
        doc["subject_id"] = str(doc["subject_id"])
    return doc


@router.get("", summary="List all cases")
async def list_cases(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["runs"].find().sort("ingested_at", -1).to_list(length=200)
    return [_serialise_case(d) for d in docs]


@router.get("/{case_id}", summary="Get a single case")
async def get_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["runs"].find_one({"run_id": case_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return _serialise_case(doc)


@router.get("/{case_id}/samples", summary="List samples for a case")
async def list_samples_for_case(
    case_id: str,
    type: str = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    case = await db["runs"].find_one({"run_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    query: dict = {"run_id": case["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}
    elif type == "test":
        query["sample_type"] = "test"

    docs = await db["samples"].find(
        query,
        {"profiles": 0},    # exclude heavy profile data from list view
    ).to_list(length=200)

    return [_serialise_sample(d) for d in docs]


@router.get("/{case_id}/krona", summary="Serve Krona HTML for a case")
async def get_krona(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    case = await db["runs"].find_one({"run_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    doc = await db["krona_files"].find_one({"run_id": case["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="No Krona file stored for this case")

    return HTMLResponse(content=doc["html"])


@router.patch("/{case_id}/review", summary="Mark a case as reviewed by the current user")
async def review_case(
    case_id: str,
    payload: ReviewPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db["runs"].update_one(
        {"run_id": case_id},
        {
            "$set": {
                "review.reviewed":    True,
                "review.reviewed_by": current_user["username"],
                "review.reviewed_at": datetime.now(timezone.utc),
                "review.notes":       payload.notes,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return {"case_id": case_id, "reviewed": True, "reviewed_by": current_user["username"]}


@router.get("/oid/{case_object_id}/krona", summary="Serve Krona HTML by case ObjectId")
async def get_krona_by_oid(
    case_object_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(case_object_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid case ObjectId")

    doc = await db["krona_files"].find_one({"run_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="No Krona file stored for this case")

    return HTMLResponse(content=doc["html"])