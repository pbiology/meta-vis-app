# app/routers/samples.py

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.models.sample import SampleResponse

from app.audit import log_audit_event
from app.constants import (
    CONTAMINANT_ELIGIBLE_RANKS,
    CONTAMINANT_NTC_READ_THRESHOLD,
)
from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/samples", tags=["samples"])


def _oid(sample_id: str) -> ObjectId:
    try:
        return ObjectId(sample_id)
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid sample_id: '{sample_id}'")


def _serialise(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "subject_id" in doc:
        doc["subject_id"] = str(doc["subject_id"])
    return doc


PAGE_SIZE = 50


@router.get("", summary="List all samples with pagination")
async def list_samples(
    page: int = 1,
    search: Annotated[str, Query(max_length=128)] = "",
    filter: str = "",
    analysis_type: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query: dict = {}

    if filter == "sample":
        query["sample_type"] = "sample"
    elif filter == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}

    if analysis_type == "shotgun":
        query["taxprofiler"] = {"$exists": True}
    elif analysis_type == "amplicon":
        query["trana"] = {"$exists": True}

    if search.strip():
        query["sample_id"] = {"$regex": re.escape(search.strip()), "$options": "i"}

    total = (
        await db["samples"].estimated_document_count()
        if not query
        else await db["samples"].count_documents(query)
    )
    skip = (page - 1) * PAGE_SIZE

    pipeline: list[dict] = [
        {"$match": query},
        {"$sort": {"order_date": -1, "ingested_at": -1}},
        {"$skip": skip},
        {"$limit": PAGE_SIZE},
        # Fetch the parent case so we can return its live review status instead
        # of the stale review field on the sample document (samples are never
        # updated when a case is marked reviewed / unreviewed).
        {
            "$lookup": {
                "from": "cases",
                "localField": "case_id",
                "foreignField": "case_id",
                "as": "_case",
            }
        },
        {"$set": {"review": {"$first": "$_case.review"}}},
        {
            "$project": {
                "_id": 1,
                "sample_id": 1,
                "sample_type": 1,
                "case_id": 1,
                "order_date": 1,
                "ingested_at": 1,
                "review": 1,
                "taxprofiler.classifiers.kraken2.pct_unclassified": 1,
                "taxprofiler.classifiers.kraken2.num_species": 1,
                "trana.nanoplot_processed.number_of_reads": 1,
            }
        },
    ]

    docs = await db["samples"].aggregate(pipeline).to_list(length=PAGE_SIZE)

    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        "items": [_serialise(doc) for doc in docs],
    }


@router.get("/{sample_id}", summary="Get full sample document")
async def get_sample(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doc = await db["samples"].find_one({"_id": _oid(sample_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    await log_audit_event(
        db,
        action="view_sample",
        actor=current_user["username"],
        resource_type="sample",
        resource_id=sample_id,
        outcome="success",
    )
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
        {"profiles": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return {
        "sample_id": sample_id,
        "profiles": doc.get("profiles", []),
    }


@router.get(
    "/{sample_id}/ntc_profiles",
    summary="Get negative control profiles matching this sample's material",
)
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

    ntc_docs = (
        await db["samples"]
        .find(
            {
                "case_id": sample["case_id"],
                "sample_type": "negative_ctrl",
                "material": sample["material"],
            },
            {"profiles": 1, "sample_id": 1},
        )
        .to_list(length=50)
    )

    profiles = []
    for ntc in ntc_docs:
        ntc_sample_id = ntc.get("sample_id", str(ntc["_id"]))
        classifiers = {}
        for p in ntc.get("profiles", []):
            clf = p.get("classifier")
            abundance_map = {
                e["taxon_id"]: e["abundance"]
                for e in p.get("profile", [])
                if e.get("abundance", 0) > 0
            }
            classifiers[clf] = abundance_map
        profiles.append(
            {
                "sample_id": ntc_sample_id,
                "classifiers": classifiers,
            }
        )

    return {
        "profiles": profiles,
        "contaminant_config": {
            "threshold": CONTAMINANT_NTC_READ_THRESHOLD,
            "eligible_ranks": sorted(CONTAMINANT_ELIGIBLE_RANKS),
        },
    }


@router.get(
    "/{sample_id}/krona", summary="Serve Krona HTML for the case this sample belongs to"
)
async def get_krona(
    sample_id: str,
    classifier: str = "kraken2",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    sample = await db["samples"].find_one(
        {"_id": _oid(sample_id)},
        {"case_id": 1, "has_krona": 1, "sample_id": 1, "trana": 1},
    )
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    if not sample.get("has_krona"):
        raise HTTPException(
            status_code=404, detail="No Krona file associated with this sample's case"
        )

    from app.database import get_blob_store

    is_trana = bool(sample.get("trana"))
    key = (
        f"krona/{sample['case_id']}/{sample['sample_id']}.html"
        if is_trana
        else f"krona/{sample['case_id']}/{classifier}.html"
    )
    html = await get_blob_store().get(key)
    if not html:
        raise HTTPException(
            status_code=404,
            detail=f"Krona file not found for classifier '{classifier}'",
        )
    return HTMLResponse(content=html)
