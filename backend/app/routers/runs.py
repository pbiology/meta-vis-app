from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database import get_db

router = APIRouter(prefix="/runs", tags=["runs"])


def _str_id(doc: dict) -> dict:
    """Convert ObjectId fields to strings for JSON serialisation."""
    doc["_id"] = str(doc["_id"])
    if "sample_ids" in doc:
        doc["sample_ids"] = [str(sid) for sid in doc["sample_ids"]]
    return doc


@router.get("", summary="List all runs")
async def list_runs(db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db["runs"].find({}, {"run_id": 1, "ingested_at": 1, "sample_ids": 1})
    runs = []
    async for doc in cursor:
        runs.append(_str_id(doc))
    return runs


@router.get("/{run_id}", summary="Get a single run by run_id string")
async def get_run(run_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await db["runs"].find_one({"run_id": run_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _str_id(doc)


@router.get("/{run_id}/samples", summary="List sample summaries for a run")
async def list_samples_for_run(run_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    run = await db["runs"].find_one({"run_id": run_id}, {"_id": 1})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    run_object_id = run["_id"]

    projection = {
        "sample": 1,
        "sample_type": 1,
        "patient_id": 1,
        "ingested_at": 1,
        "taxprofiler.kraken2": 1,
        "taxprofiler.fastqc": 1,
        "taxprofiler.fastp": 1,
        "taxprofiler.bowtie2": 1,
    }

    cursor = db["samples"].find({"run_id": run_object_id}, projection)
    samples = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["run_id"] = str(run_object_id)
        doc["patient_id"] = str(doc["patient_id"])
        samples.append(doc)
    return samples