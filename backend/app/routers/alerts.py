# app/routers/alerts.py

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from collections import defaultdict

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/outbreaks", summary="Detect viral OTUs appearing in multiple cases within a time window")
async def get_outbreaks(
    window_days: int = Query(default=14, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    # Fetch all cases with order_date
    cases = await db["cases"].find(
        {"order_date": {"$ne": None}},
        {"_id": 1, "case_id": 1, "order_date": 1}
    ).to_list(length=None)

    case_map = {str(c["_id"]): c for c in cases}
    case_dates = {str(c["_id"]): c["order_date"] for c in cases}

    # Fetch all samples, projecting only what we need
    samples = await db["samples"].find(
        {},
        {"_id": 1, "case_id": 1, "profiles": 1}
    ).to_list(length=None)

    # Build taxon -> [(case_id_str, order_date, case_name)] index
    taxon_cases: dict[tuple, list] = defaultdict(list)

    for sample in samples:
        case_id_str = str(sample["case_id"])
        order_date  = case_dates.get(case_id_str)
        if not order_date:
            continue

        case_name = case_map.get(case_id_str, {}).get("case_id", case_id_str)

        for profile in sample.get("profiles", []):
            for entry in profile.get("profile", []):
                if (
                    entry.get("superkingdom") == "Viruses"
                    and entry.get("rank") in ("species", "no rank", "serotype", None)
                    and (entry.get("abundance") or 0) > 1
                ):
                    key = (entry["taxon_id"], entry.get("name", str(entry["taxon_id"])))
                    # Avoid adding same case twice for same taxon
                    existing_case_ids = {x["case_id"] for x in taxon_cases[key]}
                    if case_id_str not in existing_case_ids:
                        taxon_cases[key].append({
                            "case_id":    case_id_str,
                            "case_name":  case_name,
                            "order_date": order_date,
                        })

    # Find clusters — cases within window_days of each other
    outbreaks = []

    for (taxon_id, taxon_name), case_entries in taxon_cases.items():
        if len(case_entries) < 2:
            continue

        # Sort by order_date
        def parse_date(d):
            if isinstance(d, str):
                return date.fromisoformat(d)
            return d

        sorted_entries = sorted(case_entries, key=lambda x: parse_date(x["order_date"]))

        # Sliding window — find any group of 2+ cases within window_days
        flagged = set()
        for i, anchor in enumerate(sorted_entries):
            anchor_date = parse_date(anchor["order_date"])
            cluster = [anchor]
            for other in sorted_entries[i + 1:]:
                other_date = parse_date(other["order_date"])
                if (other_date - anchor_date).days <= window_days:
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

    # Sort by number of flagged cases descending
    outbreaks.sort(key=lambda x: len(x["case_ids"]), reverse=True)

    return {
        "window_days": window_days,
        "outbreaks":   outbreaks,
    }