# app/routers/alerts.py

from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth.utils import get_current_user, require_role
from app.config import settings

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Simple in-memory cache — keyed by window_days
_cache: dict[int, dict] = {}
_cache_computed_at: datetime | None = None

# Cache is explicitly cleared on ignorelist changes.
# TTL is a safety net only — set high since data changes infrequently.
CACHE_TTL_SECONDS = 3600


# ============================================================================
# Models
# ============================================================================


class IgnorePayload(BaseModel):
    taxon_id: int
    taxon_name: str
    superkingdom: str = "Viruses"  # Default to Viruses, can be overridden
    reason: Optional[str] = None


class IgnoreNotePayload(BaseModel):
    reason: Optional[str] = None


# ============================================================================
# Ignorelist Endpoints (Updated with Superkingdom Filter)
# ============================================================================


@router.get("/ignorelist", summary="List ignored taxa")
async def get_ignorelist(
    superkingdom: Optional[str] = Query(
        None, description="Filter by superkingdom (e.g., 'Viruses' or 'Bacteria')"
    ),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Get ignored taxa, optionally filtered by superkingdom."""
    query = {}
    if superkingdom:
        query["superkingdom"] = superkingdom

    docs = (
        await db["outbreak_ignorelist"].find(query).sort("added_at", -1).to_list(None)
    )
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/ignorelist", summary="Add a taxon to the outbreak ignorelist")
async def add_to_ignorelist(
    payload: IgnorePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    """Add a taxon to ignorelist (writer or admin)."""
    existing = await db["outbreak_ignorelist"].find_one({"taxon_id": payload.taxon_id})
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Taxon {payload.taxon_id} is already ignored"
        )

    doc = {
        "taxon_id": payload.taxon_id,
        "taxon_name": payload.taxon_name,
        "superkingdom": payload.superkingdom,
        "reason": payload.reason,
        "added_by": current_user["username"],
        "added_at": datetime.now(timezone.utc),
    }
    result = await db["outbreak_ignorelist"].insert_one(doc)
    _cache.clear()
    doc["_id"] = str(result.inserted_id)
    return doc


@router.delete(
    "/ignorelist/{taxon_id}", summary="Remove a taxon from the outbreak ignorelist"
)
async def remove_from_ignorelist(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    """Remove a taxon from ignorelist (admin only)."""
    result = await db["outbreak_ignorelist"].delete_one({"taxon_id": taxon_id})
    _cache.clear()

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Taxon {taxon_id} not found in ignorelist"
        )

    return {"deleted": True, "taxon_id": taxon_id}


@router.patch(
    "/ignorelist/{taxon_id}", summary="Update the reason/notes for an ignored taxon"
)
async def update_ignorelist_note(
    taxon_id: int,
    payload: IgnoreNotePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),
):
    """Update reason for ignored taxon (writer or admin)."""
    result = await db["outbreak_ignorelist"].update_one(
        {"taxon_id": taxon_id},
        {"$set": {"reason": payload.reason}},
    )
    _cache.clear()

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Taxon {taxon_id} not found in ignorelist"
        )

    return {"updated": True, "taxon_id": taxon_id}


# ============================================================================
# Outbreak Detection Endpoints
# ============================================================================


def parse_date(d):
    """Parse date from string or date object."""
    if isinstance(d, str):
        return date.fromisoformat(d)
    return d


@router.get(
    "/outbreaks",
    summary="Detect multi-kingdom OTUs appearing in multiple cases within a time window",
)
async def get_outbreaks(
    window_days: int = Query(default=14, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Detect outbreaks across cases for all configured outbreak types.

    Runs each configured outbreak pattern (e.g., Viral, Bacterial) and returns
    results grouped by configuration.
    """
    global _cache_computed_at

    # Return cached result if still fresh
    now = datetime.now(timezone.utc)

    if (
        window_days in _cache
        and _cache_computed_at is not None
        and (now - _cache_computed_at).total_seconds() < CACHE_TTL_SECONDS
    ):
        return _cache[window_days]

    # Only include enabled configs
    configs = [c for c in settings.outbreak_configs if c.get("enabled", True)]

    if not configs:
        return {"window_days": window_days, "results": []}

    # Compute outbreaks for each config
    results = []
    for config in configs:
        outbreak_data = await _compute_outbreaks_for_config(config, window_days, db)
        results.append(outbreak_data)

    # Cache result
    result = {"window_days": window_days, "results": results}
    _cache[window_days] = result
    _cache_computed_at = now

    return result


async def _compute_outbreaks_for_config(
    config: dict,
    window_days: int,
    db: AsyncIOMotorDatabase,
) -> dict:
    """
    Compute outbreaks for a single config using pre-computed outbreak_taxa.

    This is fast because outbreak_taxa is a pre-computed small array,
    not the full profiles array which would require expensive unwinding.
    """
    # Load ignorelist
    ignored_docs = await db["outbreak_ignorelist"].find({}).to_list(None)
    ignored_ids = {doc["taxon_id"] for doc in ignored_docs}

    # Only fetch cases within 2× the window
    cutoff = (date.today() - timedelta(days=window_days * 2)).isoformat()
    cases = (
        await db["cases"]
        .find(
            {"order_date": {"$gte": cutoff}}, {"_id": 1, "case_id": 1, "order_date": 1}
        )
        .to_list(None)
    )

    if not cases:
        return {
            "config_name": config["name"],
            "superkingdoms": config["superkingdoms"],
            "outbreaks": [],
        }

    case_map = {str(c["_id"]): c for c in cases}
    case_oids = [c["_id"] for c in cases]

    # Fast aggregation on pre-computed outbreak_taxa
    pipeline: list[dict] = [
        # Only samples from windowed cases
        {"$match": {"case_id": {"$in": case_oids}}},
        # Unwind the small outbreak_taxa array
        {"$unwind": "$outbreak_taxa"},
        # Filter to this config's superkingdom and criteria
        {
            "$match": {
                "outbreak_taxa.superkingdom": {"$in": config["superkingdoms"]},
                "outbreak_taxa.rank": {"$in": config["min_rank"]},
                "outbreak_taxa.abundance": {"$gt": config["min_abundance"]},
                "outbreak_taxa.taxon_id": {"$nin": list(ignored_ids)},
            }
        },
        # Group by taxon and collect cases
        {
            "$group": {
                "_id": {
                    "taxon_id": "$outbreak_taxa.taxon_id",
                    "taxon_name": "$outbreak_taxa.name",
                },
                "case_ids": {"$addToSet": "$case_id"},
            }
        },
        # Only taxa seen in min_cases_threshold or more cases
        {
            "$match": {
                "$expr": {
                    "$gte": [{"$size": "$case_ids"}, config["min_cases_threshold"]]
                }
            }
        },
    ]

    raw_results = await db["samples"].aggregate(pipeline).to_list(None)

    # Build taxon_cases from aggregation results
    taxon_cases: dict[tuple, list] = {}

    for doc in raw_results:
        taxon_id = doc["_id"]["taxon_id"]
        taxon_name = doc["_id"]["taxon_name"]
        key = (taxon_id, taxon_name)

        case_entries = []
        for oid in doc["case_ids"]:
            case_id_str = str(oid)
            case_info = case_map.get(case_id_str)
            if case_info:
                case_entries.append(
                    {
                        "case_id": case_id_str,
                        "case_name": case_info["case_id"],
                        "order_date": case_info["order_date"],
                    }
                )

        taxon_cases[key] = case_entries

    # Time-window clustering
    outbreaks = []

    for (taxon_id, taxon_name), case_entries in taxon_cases.items():
        if len(case_entries) < config["min_cases_threshold"]:
            continue

        sorted_entries = sorted(case_entries, key=lambda x: parse_date(x["order_date"]))

        flagged = set()
        for i, anchor in enumerate(sorted_entries):
            anchor_date = parse_date(anchor["order_date"])
            cluster = [anchor]
            for other in sorted_entries[i + 1 :]:
                if (parse_date(other["order_date"]) - anchor_date).days <= window_days:
                    cluster.append(other)
                else:
                    break

            if len(cluster) >= config["min_cases_threshold"]:
                for entry in cluster:
                    flagged.add(entry["case_id"])

        if flagged:
            outbreaks.append(
                {
                    "taxon_id": taxon_id,
                    "taxon_name": taxon_name,
                    "case_ids": list(flagged),
                    "cases": [e for e in case_entries if e["case_id"] in flagged],
                }
            )

    outbreaks.sort(key=lambda x: len(x["case_ids"]), reverse=True)

    return {
        "config_name": config["name"],
        "superkingdoms": config["superkingdoms"],
        "outbreaks": outbreaks,
    }


# ============================================================================
# Known Pathogens Endpoints
# ============================================================================


@router.get("/pathogens", summary="List known pathogens")
async def get_pathogens(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["known_pathogens"].find().sort("added_at", -1).to_list(None)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/pathogens", summary="Add a taxon to the known pathogens list")
async def add_pathogen(
    payload: IgnorePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    existing = await db["known_pathogens"].find_one({"taxon_id": payload.taxon_id})
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Taxon {payload.taxon_id} is already on the pathogens list"
        )
    doc = {
        "taxon_id": payload.taxon_id,
        "taxon_name": payload.taxon_name,
        "superkingdom": payload.superkingdom,
        "notes": payload.reason,
        "added_by": current_user["username"],
        "added_at": datetime.now(timezone.utc),
    }
    result = await db["known_pathogens"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.delete("/pathogens/{taxon_id}", summary="Remove a taxon from the known pathogens list")
async def remove_pathogen(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),
):
    result = await db["known_pathogens"].delete_one({"taxon_id": taxon_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Taxon {taxon_id} not found in pathogens list"
        )
    return {"deleted": True, "taxon_id": taxon_id}