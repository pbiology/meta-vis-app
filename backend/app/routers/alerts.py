# app/routers/alerts.py

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from collections import defaultdict
from typing import Optional

# Simple in-memory cache — keyed by window_days
_cache: dict[int, dict] = {}
_cache_computed_at: datetime | None = None

# Cache is explicitly cleared on ingest and ignorelist changes.
# TTL is a safety net only — set high since data changes infrequently.
CACHE_TTL_SECONDS = 3600

from app.database import get_db
from app.auth.utils import get_current_user, require_role

router = APIRouter(prefix="/alerts", tags=["alerts"])


class IgnorePayload(BaseModel):
    taxon_id:   int
    taxon_name: str
    reason:     Optional[str] = None


def parse_date(d):
    if isinstance(d, str):
        return date.fromisoformat(d)
    return d


@router.get("/ignorelist", summary="List ignored taxa")
async def get_ignorelist(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["outbreak_ignorelist"].find().sort("added_at", -1).to_list(length=None)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/ignorelist", summary="Add a taxon to the outbreak ignorelist")
async def add_to_ignorelist(
    payload: IgnorePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    existing = await db["outbreak_ignorelist"].find_one({"taxon_id": payload.taxon_id})
    if existing:
        raise HTTPException(status_code=409, detail=f"Taxon {payload.taxon_id} is already ignored")
    doc = {
        "taxon_id":   payload.taxon_id,
        "taxon_name": payload.taxon_name,
        "reason":     payload.reason,
        "added_by":   current_user["username"],
        "added_at":   datetime.utcnow().isoformat(),
    }
    await db["outbreak_ignorelist"].insert_one(doc)
    _cache.clear()  # ignorelist change affects outbreak results
    doc["_id"] = str(doc["_id"])
    return doc


@router.delete("/ignorelist/{taxon_id}", summary="Remove a taxon from the outbreak ignorelist")
async def remove_from_ignorelist(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    result = await db["outbreak_ignorelist"].delete_one({"taxon_id": taxon_id})
    _cache.clear()  # ignorelist change affects outbreak results
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Taxon {taxon_id} not found in ignorelist")
    return {"deleted": True, "taxon_id": taxon_id}


class IgnoreNotePayload(BaseModel):
    reason: Optional[str] = None


@router.patch("/ignorelist/{taxon_id}", summary="Update the reason/notes for an ignored taxon")
async def update_ignorelist_note(
    taxon_id: int,
    payload: IgnoreNotePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),
):
    result = await db["outbreak_ignorelist"].update_one(
        {"taxon_id": taxon_id},
        {"$set": {"reason": payload.reason}},
    )
    _cache.clear()  # ignorelist change affects outbreak results
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Taxon {taxon_id} not found in ignorelist")
    return {"updated": True, "taxon_id": taxon_id}


@router.get("/outbreaks", summary="Detect viral OTUs appearing in multiple cases within a time window")
async def get_outbreaks(
    window_days: int = Query(default=14, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    global _cache_computed_at

    # Return cached result if still fresh
    now = datetime.utcnow()
    if (
        window_days in _cache
        and _cache_computed_at is not None
        and (now - _cache_computed_at).total_seconds() < CACHE_TTL_SECONDS
    ):
        return _cache[window_days]

    result = await _compute_outbreaks(window_days, db)

    _cache[window_days] = result
    _cache_computed_at = now
    return result


async def _compute_outbreaks(window_days: int, db: AsyncIOMotorDatabase) -> dict:
    # Load ignorelist
    ignored = await db["outbreak_ignorelist"].find({}, {"taxon_id": 1}).to_list(length=None)
    ignored_ids = {doc["taxon_id"] for doc in ignored}

    # Only fetch cases within 2× the window — bounds query regardless of total DB size
    cutoff = (date.today() - timedelta(days=window_days * 2)).isoformat()
    cases = await db["cases"].find(
        {"order_date": {"$gte": cutoff}},
        {"_id": 1, "case_id": 1, "order_date": 1}
    ).to_list(length=None)

    case_map   = {str(c["_id"]): c for c in cases}
    case_dates = {str(c["_id"]): c["order_date"] for c in cases}

    if not case_dates:
        return {"window_days": window_days, "outbreaks": []}

    samples = await db["samples"].find(
        {"case_id": {"$in": [c["_id"] for c in cases]}},
        {"_id": 1, "case_id": 1, "profiles": 1}
    ).to_list(length=None)

    taxon_cases: dict[tuple, list] = defaultdict(list)

    for sample in samples:
        case_id_str = str(sample["case_id"])
        order_date  = case_dates.get(case_id_str)
        if not order_date:
            continue
        case_name = case_map.get(case_id_str, {}).get("case_id", case_id_str)

        for profile in sample.get("profiles", []):
            for entry in profile.get("profile", []):
                taxon_id = entry["taxon_id"]
                if taxon_id in ignored_ids:
                    continue
                if (
                    entry.get("superkingdom") == "Viruses"
                    and entry.get("rank") in ("species", "no rank", "serotype", None)
                    and (entry.get("abundance") or 0) > 1
                ):
                    key = (taxon_id, entry.get("name", str(taxon_id)))
                    existing_case_ids = {x["case_id"] for x in taxon_cases[key]}
                    if case_id_str not in existing_case_ids:
                        taxon_cases[key].append({
                            "case_id":    case_id_str,
                            "case_name":  case_name,
                            "order_date": order_date,
                        })

    outbreaks = []

    for (taxon_id, taxon_name), case_entries in taxon_cases.items():
        if len(case_entries) < 2:
            continue

        sorted_entries = sorted(case_entries, key=lambda x: parse_date(x["order_date"]))

        flagged = set()
        for i, anchor in enumerate(sorted_entries):
            anchor_date = parse_date(anchor["order_date"])
            cluster = [anchor]
            for other in sorted_entries[i + 1:]:
                if (parse_date(other["order_date"]) - anchor_date).days <= window_days:
                    cluster.append(other)
                else:
                    break
            if len(cluster) >= 2:
                for entry in cluster:
                    flagged.add(entry["case_id"])

        if flagged:
            outbreaks.append({
                "taxon_id":   taxon_id,
                "taxon_name": taxon_name,
                "case_ids":   list(flagged),
                "cases":      [e for e in case_entries if e["case_id"] in flagged],
            })

    outbreaks.sort(key=lambda x: len(x["case_ids"]), reverse=True)

    return {"window_days": window_days, "outbreaks": outbreaks}