# app/routers/ntc.py

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Literal

from app.database import get_db
from app.auth.utils import get_current_user
from app.constants import HOST_TAXON_IDS

router = APIRouter(prefix="/ntc", tags=["ntc"])


@router.get("/trends", summary="NTC contamination trends across cases")
async def get_ntc_trends(
    material: Literal["DNA", "RNA"] = Query(..., description="DNA or RNA"),
    window_days: int = Query(default=90, ge=7, le=365),
    min_reads: int = Query(default=3, ge=1),
    min_case_pct: float = Query(default=0.10, ge=0.0, le=1.0),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    """
    Return NTC trend data for the given material type within a rolling window.

    Two datasets are returned:
    - read_counts: total kraken2 classified reads per NTC per case, for the
      scatter chart showing overall contamination load over time.
    - recurring_taxa: taxa appearing in >= min_case_pct of cases with
      abundance > min_reads, for the line chart showing specific contaminants.
    """
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    # --- Fetch all NTC samples in window for this material ---
    # We only look at kraken2 profiles. The classifier name is stored on the
    # profile subdocument, so we filter in the aggregation pipeline below.
    ntc_docs = (
        await db["samples"]
        .find(
            {
                "sample_type": "negative_ctrl",
                "material": material,
                "order_date": {"$gte": cutoff},
            },
            {
                "sample_id": 1,
                "case_id_str": 1,
                "order_date": 1,
                "taxprofiler.classifiers.kraken2": 1,
                "profiles": 1,
            },
        )
        .sort("order_date", 1)
        .to_list(None)
    )

    if not ntc_docs:
        return {
            "material": material,
            "window_days": window_days,
            "total_ntcs": 0,
            "read_counts": [],
            "recurring_taxa": [],
        }

    total_ntcs = len(ntc_docs)
    min_case_count = max(1, round(total_ntcs * min_case_pct))

    # --- Build read_counts: one entry per NTC ---
    read_counts: list[dict] = []
    for doc in ntc_docs:
        kraken2_qc = (
            doc.get("taxprofiler", {}).get("classifiers", {}).get("kraken2", {})
        )
        classified = kraken2_qc.get("classified_reads")
        read_counts.append(
            {
                "sample_id": doc["sample_id"],
                "case_id": doc["case_id_str"],
                "order_date": doc.get("order_date"),
                "classified_reads": classified,
            }
        )

    # --- Build recurring_taxa: aggregate across NTC profiles ---
    # For each NTC find its kraken2 profile and collect taxa above min_reads.
    # Then keep only taxa seen in >= min_case_count distinct cases.
    taxon_cases: dict[int, dict] = {}  # taxon_id -> {name, superkingdom, cases}

    for doc in ntc_docs:
        case_id = doc["case_id_str"]
        kraken2_profile: list[dict] = []
        for p in doc.get("profiles", []):
            if p.get("classifier") == "kraken2":
                kraken2_profile = p.get("profile", [])
                break

        seen_in_this_doc: set[int] = set()
        for entry in kraken2_profile:
            taxon_id = entry.get("taxon_id")
            if taxon_id is None or taxon_id in seen_in_this_doc:
                continue
            if taxon_id in HOST_TAXON_IDS:
                continue
            abundance = entry.get("abundance", 0)
            if abundance <= min_reads:
                continue
            seen_in_this_doc.add(taxon_id)

            if taxon_id not in taxon_cases:
                taxon_cases[taxon_id] = {
                    "taxon_id": taxon_id,
                    "taxon_name": entry.get("name", str(taxon_id)),
                    "superkingdom": entry.get("superkingdom"),
                    "occurrences": [],
                }
            taxon_cases[taxon_id]["occurrences"].append(
                {
                    "case_id": case_id,
                    "sample_id": doc["sample_id"],
                    "order_date": doc.get("order_date"),
                    "abundance": abundance,
                }
            )

    # Filter to taxa seen in enough distinct cases
    recurring_taxa: list[dict] = []
    for taxon in taxon_cases.values():
        distinct_cases = len({o["case_id"] for o in taxon["occurrences"]})
        if distinct_cases >= min_case_count:
            # Sort occurrences by date for clean chart rendering
            taxon["occurrences"].sort(key=lambda o: o["order_date"] or "")
            taxon["case_count"] = distinct_cases
            recurring_taxa.append(taxon)

    # Sort by case_count descending so the most prevalent contaminants come first
    recurring_taxa.sort(key=lambda t: t["case_count"], reverse=True)

    return {
        "material": material,
        "window_days": window_days,
        "total_ntcs": total_ntcs,
        "min_case_count": min_case_count,
        "read_counts": read_counts,
        "recurring_taxa": recurring_taxa,
    }
