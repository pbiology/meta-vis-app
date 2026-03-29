from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import os

from app.database import get_db

router = APIRouter(prefix="/samples", tags=["samples"])


def _oid(sample_id: str) -> ObjectId:
    try:
        return ObjectId(sample_id)
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid sample_id: '{sample_id}'")


def _serialise(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "run_id" in doc:
        doc["run_id"] = str(doc["run_id"])
    if "patient_id" in doc:
        doc["patient_id"] = str(doc["patient_id"])
    return doc


@router.get("/{sample_id}", summary="Get full sample document")
async def get_sample(sample_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await db["samples"].find_one({"_id": _oid(sample_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return _serialise(doc)


@router.get("/{sample_id}/profile", summary="Get taxonomic profile(s) for a sample")
async def get_profile(sample_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
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


@router.get("/{sample_id}/krona", summary="Serve Krona HTML for a sample")
async def get_krona(sample_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await db["samples"].find_one(
        {"_id": _oid(sample_id)},
        {"krona_path": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")

    path = doc.get("krona_path")
    if not path:
        raise HTTPException(status_code=404, detail="No Krona file associated with this sample")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Krona file not found on disk: {path}")

    return FileResponse(path, media_type="text/html")
