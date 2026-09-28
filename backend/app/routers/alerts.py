# app/routers/alerts.py

import asyncio
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.cache import get_cache_version
from app.database import get_db
from app.auth.utils import get_current_user
from app.config import settings
from app.taxon_lists import store as taxon_lists
from app.taxon_lists.kinds import OUTBREAK_IGNORELIST

router = APIRouter(prefix="/alerts", tags=["alerts"])

# key → (db_version, computed_at, result)
# Valid when stored db_version matches the shared MongoDB counter and within TTL.
_cache: dict[tuple, tuple[int, datetime, dict]] = {}
_cache_lock = asyncio.Lock()

# TTL is a safety net for rolling-window staleness (cases aging in/out of window).
# Primary invalidation is the shared db_version counter.
CACHE_TTL_SECONDS = 3600


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
    analysis_types: list[str] | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Detect outbreaks across cases for all configured outbreak types.

    Runs each configured outbreak pattern (e.g., Viral, Bacterial) and returns
    results grouped by configuration.
    """
    now = datetime.now(timezone.utc)
    cache_key = (window_days, tuple(sorted(analysis_types)) if analysis_types else ())
    current_version = await get_cache_version(db)

    # Fast path: serve from cache without acquiring the lock.
    if cache_key in _cache:
        stored_version, computed_at, cached_result = _cache[cache_key]
        if (
            stored_version == current_version
            and (now - computed_at).total_seconds() < CACHE_TTL_SECONDS
        ):
            return cached_result

    configs = [c for c in settings.outbreak_configs if c.get("enabled", True)]
    if not configs:
        return {"window_days": window_days, "results": []}

    async with _cache_lock:
        # Re-check after acquiring the lock: another coroutine may have computed
        # the result while we were waiting.
        current_version = await get_cache_version(db)
        now = datetime.now(timezone.utc)
        if cache_key in _cache:
            stored_version, computed_at, cached_result = _cache[cache_key]
            if (
                stored_version == current_version
                and (now - computed_at).total_seconds() < CACHE_TTL_SECONDS
            ):
                return cached_result

        results = []
        for config in configs:
            outbreak_data = await _compute_outbreaks_for_config(
                config, window_days, db, analysis_types
            )
            results.append(outbreak_data)

        result = {"window_days": window_days, "results": results}
        _cache[cache_key] = (current_version, now, result)

    return result


async def _compute_outbreaks_for_config(
    config: dict,
    window_days: int,
    db: AsyncIOMotorDatabase,
    analysis_types: list[str] | None = None,
) -> dict:
    """
    Compute outbreaks for a single config using pre-computed outbreak_taxa.

    This is fast because outbreak_taxa is a pre-computed small array,
    not the full profiles array which would require expensive unwinding.
    """
    ignored_ids = await taxon_lists.taxon_ids(db, OUTBREAK_IGNORELIST)

    # Only fetch analyses within 2× the window.
    # Stream the cursor instead of materializing the full list so that
    # large windows don't load every document into memory at once.
    #
    # Driven from case_analysis rather than cases: order_date, analysis_type
    # and is_latest all live there. Restricting to latest analyses means a
    # superseded run's taxa cannot contribute to an outbreak signal.
    cutoff = (date.today() - timedelta(days=window_days * 2)).isoformat()
    case_query: dict = {"is_latest": True, "order_date": {"$gte": cutoff}}
    if analysis_types:
        case_query["analysis_type"] = {"$in": analysis_types}

    case_map: dict = {}
    case_id_strs: list[str] = []
    async for c in db["case_analysis"].find(
        case_query, {"_id": 1, "case_id": 1, "order_date": 1}
    ):
        case_map[c["case_id"]] = c
        case_id_strs.append(c["case_id"])

    if not case_id_strs:
        return {
            "config_name": config["name"],
            "superkingdoms": config["superkingdoms"],
            "outbreaks": [],
        }

    # Fast aggregation on pre-computed outbreak_taxa
    pipeline: list[dict] = [
        # Only samples from the latest analyses of windowed cases. The
        # $addToSet on case_id below then counts distinct *clinical cases*:
        # a case sequenced twice contributes one entry, not two.
        {"$match": {"case_id": {"$in": case_id_strs}, "is_latest_analysis": True}},
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

    # Bounded by group-by cardinality (one row per outbreak taxon after filters).
    raw_results = await db["samples"].aggregate(pipeline).to_list(None)

    # Build taxon_cases from aggregation results
    taxon_cases: dict[tuple, list] = {}

    for doc in raw_results:
        taxon_id = doc["_id"]["taxon_id"]
        taxon_name = doc["_id"]["taxon_name"]
        key = (taxon_id, taxon_name)

        case_entries = []
        for cid in doc["case_ids"]:
            case_info = case_map.get(cid)
            if case_info:
                case_entries.append(
                    {
                        "case_id": cid,
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
