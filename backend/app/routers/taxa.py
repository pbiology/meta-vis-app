# app/routers/taxa.py

from datetime import date, timedelta, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
import httpx
from functools import lru_cache
import time


from app.database import get_db
from app.auth.utils import get_current_user, require_role

router = APIRouter(prefix="/taxa", tags=["taxa"])


class ClinicalNotesPayload(BaseModel):
    clinical_notes: Optional[str] = None


# Simple in-memory cache: taxon_id -> (timestamp, data)
_links_cache: dict[int, tuple[float, list]] = {}
LINKS_CACHE_TTL = 86400  # 24 hours — external links change rarely


@router.get(
    "/{taxon_id}/external_links",
    summary="Get curated external links for a taxon from NCBI",
)
async def get_external_links(
    taxon_id: int,
    _user: dict = Depends(get_current_user),
):
    now = time.time()
    if taxon_id in _links_cache:
        ts, data = _links_cache[taxon_id]
        if now - ts < LINKS_CACHE_TTL:
            return {"taxon_id": taxon_id, "links": data}

    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{taxon_id}/links"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            raw = resp.json()
    except Exception:
        return {"taxon_id": taxon_id, "links": []}

    # Response is a flat object: {"tax_id": "...", "wikipedia": "https://...", ...}
    # Convert to a list of {name, url} dicts, skipping the tax_id field.
    links = [
        {"name": key.replace("_", " ").title(), "url": value}
        for key, value in raw.items()
        if key != "tax_id" and isinstance(value, str)
    ]

    _links_cache[taxon_id] = (now, links)
    return {"taxon_id": taxon_id, "links": links}


@router.get("/{taxon_id}", summary="Get taxon reference data")
async def get_taxon(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["taxa"].find_one({"taxon_id": taxon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Taxon {taxon_id} not found in the taxa collection. "
                "Run load_taxonomy.py to populate reference data."
            ),
        )
    # Flag to the frontend that this record has not been loaded from the
    # NCBI dump yet — only a skeleton from ingest-time fallback exists.
    doc["needs_taxonomy_refresh"] = doc.get("taxdump_version") is None
    return doc


@router.patch(
    "/{taxon_id}/clinical_notes",
    summary="Add or update clinical notes for a taxon",
)
async def update_clinical_notes(
    taxon_id: int,
    payload: ClinicalNotesPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    now = datetime.now(timezone.utc)
    result = await db["taxa"].update_one(
        {"taxon_id": taxon_id},
        {
            "$set": {
                "clinical_notes": payload.clinical_notes,
                "clinical_notes_author": current_user["username"]
                if payload.clinical_notes
                else None,
                "clinical_notes_updated_at": now if payload.clinical_notes else None,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Taxon {taxon_id} not found")
    return {"updated": True, "taxon_id": taxon_id}


@router.get(
    "/{taxon_id}/occurrences",
    summary="Cases and samples in which this taxon has been detected",
)
async def get_taxon_occurrences(
    taxon_id: int,
    window_days: int = Query(default=90, ge=7, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Returns cases where this taxon was detected within a rolling time window,
    along with per-classifier read counts. Mirrors the sliding-window approach
    used by outbreak detection.
    """
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    pipeline: list[dict] = [
        # Scope to the time window and samples that contain the taxon
        {
            "$match": {
                "order_date": {"$gte": cutoff},
                "all_taxon_ids": taxon_id,
            }
        },
        # Unwind profiles to find per-classifier read counts
        {"$unwind": "$profiles"},
        {"$unwind": "$profiles.profile"},
        {"$match": {"profiles.profile.taxon_id": taxon_id}},
        # Group per sample+classifier
        {
            "$group": {
                "_id": {
                    "sample_id": "$sample.sample_id",
                    "case_id_str": "$case_id_str",
                    "order_date": "$order_date",
                    "classifier": "$profiles.classifier",
                },
                "abundance": {"$max": "$profiles.profile.abundance"},
            }
        },
        # Roll up to case level
        {
            "$group": {
                "_id": {
                    "case_id_str": "$_id.case_id_str",
                    "order_date": "$_id.order_date",
                },
                "samples": {
                    "$push": {
                        "sample_id": "$_id.sample_id",
                        "classifier": "$_id.classifier",
                        "abundance": "$abundance",
                    }
                },
                "sample_count": {"$addToSet": "$_id.sample_id"},
            }
        },
        {"$sort": {"_id.order_date": -1}},
        {"$limit": 200},
        {
            "$project": {
                "_id": 0,
                "case_id": "$_id.case_id_str",
                "order_date": "$_id.order_date",
                "sample_count": {"$size": "$sample_count"},
                "samples": 1,
            }
        },
    ]

    cases = await db["samples"].aggregate(pipeline).to_list(length=200)

    return {
        "taxon_id": taxon_id,
        "window_days": window_days,
        "total_cases": len(cases),
        "cases": cases,
    }
