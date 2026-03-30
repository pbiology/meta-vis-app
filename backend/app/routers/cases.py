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
    # case_id is already a plain string — no conversion needed
    return doc


def _serialise_sample(doc: dict) -> dict:
    doc["_id"]     = str(doc["_id"])
    doc["case_id"] = str(doc["case_id"])
    if doc.get("subject_id"):
        doc["subject_id"] = str(doc["subject_id"])
    return doc


@router.get("", summary="List all cases")
async def list_cases(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["cases"].find().sort("ingested_at", -1).to_list(length=200)
    return [_serialise_case(d) for d in docs]


@router.get("/{case_id}", summary="Get a single case")
async def get_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["cases"].find_one({"case_id": case_id})
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
    case = await db["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    query: dict = {"case_id": case["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}
    elif type == "test":
        query["sample_type"] = "test"

    docs = await db["samples"].find(query).to_list(length=200)

    HOST_TAXON_IDS = {9606, 1, 0, 131567}

    def top_taxa(doc: dict, n: int = 3) -> list:
        all_entries = doc.get("profiles", [{}])[0].get("profile", []) if doc.get("profiles") else []
        host_reads = next((e["abundance"] for e in all_entries if e.get("name") == "Homo sapiens"), 0)
        unclass_reads = sum(e["abundance"] for e in all_entries if e.get("name") == "unclassified")
        total_reads = sum(e["abundance"] for e in all_entries)
        non_host_total = total_reads - host_reads - unclass_reads
        non_host_entries = [
            e for e in all_entries
            if e.get("taxon_id") not in HOST_TAXON_IDS
            and e.get("name") != "unclassified"
            and not (e.get("name") or "").startswith("unclassified ")
        ]
        non_host_entries.sort(key=lambda e: e.get("abundance", 0), reverse=True)
        return [
            {
                "name": e["name"],
                "superkingdom": e.get("superkingdom"),
                "abundance": e["abundance"],
                "pct": round(e["abundance"] / non_host_total * 100, 3) if non_host_total else None,
            }
            for e in non_host_entries[:n]
        ]

    result = []
    for doc in docs:
        doc["top_taxa"] = top_taxa(doc)
        doc.pop("profiles", None)
        result.append(_serialise_sample(doc))
    return result


@router.get("/{case_id}/krona", summary="Serve Krona HTML for a case")
async def get_krona(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    case = await db["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    doc = await db["krona_files"].find_one({"case_id": case["_id"]})
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
    result = await db["cases"].update_one(
        {"case_id": case_id},
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


@router.delete("/{case_id}/review", summary="Remove review from a case")
async def unreview_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db["cases"].update_one(
        {"case_id": case_id},
        {
            "$set": {
                "review.reviewed":    False,
                "review.reviewed_by": None,
                "review.reviewed_at": None,
                "review.notes":       None,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return {"case_id": case_id, "reviewed": False}


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

    doc = await db["krona_files"].find_one({"case_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="No Krona file stored for this case")

    return HTMLResponse(content=doc["html"])
