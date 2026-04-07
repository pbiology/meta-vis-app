# app/routers/subjects.py

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", summary="List all subjects")
async def list_subjects(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cursor = db["subjects"].find({}).sort("created_at", -1)
    subjects = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        subjects.append(doc)
    return subjects


@router.get(
    "/{subject_id}/samples", summary="All samples for a subject, sorted by order_date"
)
async def list_samples_for_subject(
    subject_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    subject = await db["subjects"].find_one({"subject_id": subject_id})
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

    projection = {
        "sample": 1,
        "sample_type": 1,
        "run_id": 1,
        "order_date": 1,
        "ingested_at": 1,
        "review": 1,
        "taxprofiler.kraken2": 1,
        "taxprofiler.fastqc": 1,
        "taxprofiler.fastp": 1,
        "taxprofiler.bowtie2": 1,
    }

    cursor = (
        db["samples"]
        .find({"subject_id": subject["_id"]}, projection)
        .sort([("order_date", -1), ("ingested_at", -1)])
    )

    samples = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["run_id"] = str(doc["run_id"])
        doc["subject_id"] = str(subject["_id"])
        samples.append(doc)
    return samples
