# app/routers/runs.py

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/runs", tags=["runs"])

CONTROL_TYPES = {"negative_ctrl", "positive_ctrl"}


def _str_id(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "sample_ids" in doc:
        doc["sample_ids"] = [str(sid) for sid in doc["sample_ids"]]
    return doc


@router.get("", summary="List all runs (newest first)")
async def list_runs(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    cursor = db["runs"].find(
        {},
        {"run_id": 1, "ingested_at": 1, "sample_ids": 1},
    ).sort("ingested_at", -1)
    return [_str_id(doc) async for doc in cursor]


@router.get("/{run_id}", summary="Get a single run by run_id string")
async def get_run(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["runs"].find_one({"run_id": run_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _str_id(doc)


@router.get("/{run_id}/samples", summary="List sample summaries for a run")
async def list_samples_for_run(
    run_id: str,
    type: Optional[str] = Query(
        default=None,
        description="Filter: 'test', 'controls' (neg+pos), 'negative_ctrl', 'positive_ctrl'",
    ),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    run = await db["runs"].find_one({"run_id": run_id}, {"_id": 1})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    query: dict = {"run_id": run["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": list(CONTROL_TYPES)}
    elif type is not None:
        query["sample_type"] = type

    projection = {
        "sample": 1,
        "sample_type": 1,
        "subject_id": 1,
        "order_date": 1,
        "ingested_at": 1,
        "review": 1,
        "taxprofiler.kraken2": 1,
        "taxprofiler.fastqc": 1,
        "taxprofiler.fastp": 1,
        "taxprofiler.bowtie2": 1,
    }

    cursor = db["samples"].find(query, projection).sort(
        [("order_date", -1), ("ingested_at", -1)]
    )

    samples = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["run_id"] = str(run["_id"])
        doc["subject_id"] = str(doc["subject_id"])
        samples.append(doc)
    return samples