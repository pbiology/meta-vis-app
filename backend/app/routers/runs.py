# app/routers/runs.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/runs", tags=["runs"])


def _serialise_run(doc: dict) -> dict:
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


@router.get("", summary="List all runs")
async def list_runs(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["runs"].find().sort("ingested_at", -1).to_list(length=200)
    return [_serialise_run(d) for d in docs]


@router.get("/{run_id}", summary="Get a single run")
async def get_run(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["runs"].find_one({"run_id": run_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _serialise_run(doc)


@router.get("/{run_id}/samples", summary="List samples for a run")
async def list_samples_for_run(
    run_id: str,
    type: str = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    run = await db["runs"].find_one({"run_id": run_id})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    query: dict = {"run_id": run["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}
    elif type == "test":
        query["sample_type"] = "test"

    docs = await db["samples"].find(
        query,
        {"profiles": 0},    # exclude heavy profile data from list view
    ).to_list(length=200)

    return [_serialise_sample(d) for d in docs]


@router.get("/{run_id}/krona", summary="Serve Krona HTML for a run")
async def get_krona(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    run = await db["runs"].find_one({"run_id": run_id})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    doc = await db["krona_files"].find_one({"run_id": run["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="No Krona file stored for this run")

    return HTMLResponse(content=doc["html"])


@router.get("/oid/{run_object_id}/krona", summary="Serve Krona HTML by run ObjectId")
async def get_krona_by_oid(
    run_object_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        oid = ObjectId(run_object_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid run ObjectId")

    doc = await db["krona_files"].find_one({"run_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="No Krona file stored for this run")

    return HTMLResponse(content=doc["html"])