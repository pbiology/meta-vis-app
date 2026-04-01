# app/routers/samples.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
import os
from app.models.sample import SampleResponse

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
    if "case_id" in doc:
        doc["case_id"] = str(doc["case_id"])
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
    doc = _serialise(doc)
    return SampleResponse.model_validate(doc).model_dump(mode="json")


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

@router.get("/{sample_id}/ntc_profiles", summary="Get negative control profiles matching this sample's material")
async def get_ntc_profiles(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    sample = await db["samples"].find_one(
        {"_id": _oid(sample_id)},
        {"case_id": 1, "material": 1},
    )
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")

    ntc_docs = await db["samples"].find(
        {
            "case_id":     sample["case_id"],
            "sample_type": "negative_ctrl",
            "material":    sample["material"],
        },
        {"profiles": 1, "sample": 1},
    ).to_list(length=50)

    result = []
    for ntc in ntc_docs:
        ntc_sample_id = ntc.get("sample", {}).get("sample_id", str(ntc["_id"]))
        classifiers = {}
        for p in ntc.get("profiles", []):
            clf = p.get("classifier")
            abundance_map = {
                e["taxon_id"]: e["abundance"]
                for e in p.get("profile", [])
                if e.get("abundance", 0) > 0
            }
            classifiers[clf] = abundance_map
        result.append({
            "sample_id":   ntc_sample_id,
            "classifiers": classifiers,
        })

    return result

@router.get("/{sample_id}/krona", summary="Serve Krona HTML for the case this sample belongs to")
async def get_krona(
    sample_id: str,
    classifier: str = "kraken2",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from fastapi.responses import HTMLResponse
    sample = await db["samples"].find_one({"_id": _oid(sample_id)}, {"case_id": 1, "has_krona": 1})
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    if not sample.get("has_krona"):
        raise HTTPException(status_code=404, detail="No Krona file associated with this sample's case")
    doc = await db["krona_files"].find_one({
        "case_id":    sample["case_id"],
        "classifier": classifier,
    })
    if not doc:
        raise HTTPException(status_code=404, detail=f"Krona file not found for classifier '{classifier}'")
    return HTMLResponse(content=doc["html"])