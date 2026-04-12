# app/routers/ntc.py

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Literal, Optional

from app.audit import log_audit_event
from app.database import get_db
from app.auth.utils import get_current_user, require_role
from app.constants import HOST_TAXON_IDS

router = APIRouter(prefix="/ntc", tags=["ntc"])

# ---------------------------------------------------------------------------
# Simple in-memory cache for contaminant alert results.
# Invalidated on ingest and on any change to the contaminants list.
# ---------------------------------------------------------------------------

_contaminant_alert_cache: dict[int, dict] = {}  # window_days -> payload


def invalidate_contaminant_cache() -> None:
    _contaminant_alert_cache.clear()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class IgnorePayload(BaseModel):
    taxon_id: int
    taxon_name: str
    superkingdom: Optional[str] = None
    reason: Optional[str] = None


class IgnoreNotePayload(BaseModel):
    reason: Optional[str] = None


class ContaminantPayload(BaseModel):
    taxon_id: int
    taxon_name: str
    superkingdom: Optional[str] = None
    min_reads: int = 3
    notes: Optional[str] = None


class ContaminantUpdatePayload(BaseModel):
    min_reads: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# NTC ignorelist endpoints
# ---------------------------------------------------------------------------


@router.get("/ignorelist", summary="List NTC ignored taxa")
async def get_ntc_ignorelist(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list:
    docs = await db["ntc_ignorelist"].find().sort("added_at", -1).to_list(length=1000)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/ignorelist", summary="Add a taxon to the NTC ignorelist")
async def add_to_ntc_ignorelist(
    payload: IgnorePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> dict:
    existing = await db["ntc_ignorelist"].find_one({"taxon_id": payload.taxon_id})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Taxon {payload.taxon_id} is already on the NTC ignorelist",
        )
    on_contaminants = await db["ntc_known_contaminants"].find_one(
        {"taxon_id": payload.taxon_id}
    )
    if on_contaminants:
        raise HTTPException(
            status_code=409,
            detail=f"Taxon {payload.taxon_id} is already on the known contaminants list. "
            f"Remove it from there before adding it to the ignorelist.",
        )
    doc = {
        "taxon_id": payload.taxon_id,
        "taxon_name": payload.taxon_name,
        "superkingdom": payload.superkingdom,
        "reason": payload.reason,
        "added_by": current_user["username"],
        "added_at": datetime.now(timezone.utc),
    }
    result = await db["ntc_ignorelist"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    # Ignoring a taxon affects trend calculations — invalidate cache
    invalidate_contaminant_cache()
    await log_audit_event(
        db,
        action="ntc_ignorelist_add",
        actor=current_user["username"],
        resource_type="ntc_ignorelist_entry",
        resource_id=str(payload.taxon_id),
        outcome="success",
    )
    return doc


@router.patch("/ignorelist/{taxon_id}", summary="Update reason for an ignored taxon")
async def update_ntc_ignorelist_note(
    taxon_id: int,
    payload: IgnoreNotePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> dict:
    result = await db["ntc_ignorelist"].update_one(
        {"taxon_id": taxon_id},
        {"$set": {"reason": payload.reason}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Taxon {taxon_id} not found in NTC ignorelist"
        )
    await log_audit_event(
        db,
        action="ntc_ignorelist_update",
        actor=current_user["username"],
        resource_type="ntc_ignorelist_entry",
        resource_id=str(taxon_id),
        outcome="success",
    )
    return {"updated": True, "taxon_id": taxon_id}


@router.delete(
    "/ignorelist/{taxon_id}", summary="Remove a taxon from the NTC ignorelist"
)
async def remove_from_ntc_ignorelist(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
) -> dict:
    result = await db["ntc_ignorelist"].delete_one({"taxon_id": taxon_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Taxon {taxon_id} not found in NTC ignorelist"
        )
    invalidate_contaminant_cache()
    await log_audit_event(
        db,
        action="ntc_ignorelist_remove",
        actor=current_user["username"],
        resource_type="ntc_ignorelist_entry",
        resource_id=str(taxon_id),
        outcome="success",
    )
    return {"deleted": True, "taxon_id": taxon_id}


# ---------------------------------------------------------------------------
# NTC known contaminants endpoints
# ---------------------------------------------------------------------------


@router.get("/contaminants", summary="List NTC known contaminants")
async def get_ntc_contaminants(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list:
    docs = (
        await db["ntc_known_contaminants"]
        .find()
        .sort("added_at", -1)
        .to_list(length=1000)
    )
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@router.post("/contaminants", summary="Add a taxon to the NTC known contaminants list")
async def add_ntc_contaminant(
    payload: ContaminantPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> dict:
    existing = await db["ntc_known_contaminants"].find_one(
        {"taxon_id": payload.taxon_id}
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Taxon {payload.taxon_id} is already on the known contaminants list",
        )
    on_ignorelist = await db["ntc_ignorelist"].find_one({"taxon_id": payload.taxon_id})
    if on_ignorelist:
        raise HTTPException(
            status_code=409,
            detail=f"Taxon {payload.taxon_id} is already on the NTC ignorelist. "
            f"Remove it from there before adding it to the known contaminants list.",
        )
    doc = {
        "taxon_id": payload.taxon_id,
        "taxon_name": payload.taxon_name,
        "superkingdom": payload.superkingdom,
        "min_reads": payload.min_reads,
        "notes": payload.notes,
        "added_by": current_user["username"],
        "added_at": datetime.now(timezone.utc),
    }
    result = await db["ntc_known_contaminants"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    invalidate_contaminant_cache()
    await log_audit_event(
        db,
        action="ntc_contaminant_add",
        actor=current_user["username"],
        resource_type="ntc_contaminant",
        resource_id=str(payload.taxon_id),
        outcome="success",
    )
    return doc


@router.patch(
    "/contaminants/{taxon_id}", summary="Update min_reads or notes for a contaminant"
)
async def update_ntc_contaminant(
    taxon_id: int,
    payload: ContaminantUpdatePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> dict:
    updates: dict = {}
    if payload.min_reads is not None:
        updates["min_reads"] = payload.min_reads
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    result = await db["ntc_known_contaminants"].update_one(
        {"taxon_id": taxon_id}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Taxon {taxon_id} not found in known contaminants list",
        )
    invalidate_contaminant_cache()
    await log_audit_event(
        db,
        action="ntc_contaminant_update",
        actor=current_user["username"],
        resource_type="ntc_contaminant",
        resource_id=str(taxon_id),
        outcome="success",
    )
    return {"updated": True, "taxon_id": taxon_id}


@router.delete(
    "/contaminants/{taxon_id}",
    summary="Remove a taxon from the NTC known contaminants list",
)
async def remove_ntc_contaminant(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
) -> dict:
    result = await db["ntc_known_contaminants"].delete_one({"taxon_id": taxon_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Taxon {taxon_id} not found in known contaminants list",
        )
    invalidate_contaminant_cache()
    await log_audit_event(
        db,
        action="ntc_contaminant_remove",
        actor=current_user["username"],
        resource_type="ntc_contaminant",
        resource_id=str(taxon_id),
        outcome="success",
    )
    return {"deleted": True, "taxon_id": taxon_id}


# ---------------------------------------------------------------------------
# Contaminant alerts — which cases have NTCs containing known contaminants
# ---------------------------------------------------------------------------


@router.get(
    "/contaminant-alerts",
    summary="Cases whose NTCs contain known contaminants above their min_reads threshold",
)
async def get_contaminant_alerts(
    window_days: int = Query(default=90, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    if window_days in _contaminant_alert_cache:
        return _contaminant_alert_cache[window_days]

    contaminants = await db["ntc_known_contaminants"].find().to_list(length=1000)
    if not contaminants:
        result: dict = {"alerts": [], "contaminant_case_ids": []}
        _contaminant_alert_cache[window_days] = result
        return result

    from datetime import date

    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    # For each contaminant find NTC samples where its abundance exceeds min_reads.
    # We iterate profiles in Python rather than using $unwind because the NTC
    # sample count is small and we need per-contaminant min_reads thresholds.
    ntc_docs = (
        await db["samples"]
        .find(
            {"sample_type": "negative_ctrl", "order_date": {"$gte": cutoff}},
            {
                "sample_id": 1,
                "case_id": 1,
                "case_id_str": 1,
                "order_date": 1,
                "profiles": 1,
            },
        )
        .sort("order_date", -1)
        .to_list(None)
    )

    # Build a lookup: taxon_id -> contaminant doc
    contaminant_map = {c["taxon_id"]: c for c in contaminants}

    # taxon_id -> list of affected NTC occurrences
    hits: dict[int, list[dict]] = {c["taxon_id"]: [] for c in contaminants}

    for doc in ntc_docs:
        for p in doc.get("profiles", []):
            if p.get("classifier") != "kraken2":
                continue
            for entry in p.get("profile", []):
                tid = entry.get("taxon_id")
                if tid not in contaminant_map:
                    continue
                min_r = contaminant_map[tid]["min_reads"]
                if entry.get("abundance", 0) > min_r:
                    hits[tid].append(
                        {
                            "case_id": doc["case_id_str"],
                            "case_oid": str(doc["case_id"]),
                            "sample_id": doc["sample_id"],
                            "order_date": doc.get("order_date"),
                            "abundance": entry["abundance"],
                        }
                    )

    alerts = []
    all_case_ids: set[str] = set()
    for contaminant in contaminants:
        tid = contaminant["taxon_id"]
        occurrences = hits[tid]
        if not occurrences:
            continue
        case_ids = list({o["case_id"] for o in occurrences})
        # Use MongoDB ObjectIds for cross-referencing with the case list
        case_oids = list({o["case_oid"] for o in occurrences})
        all_case_ids.update(case_oids)
        alerts.append(
            {
                "taxon_id": tid,
                "taxon_name": contaminant["taxon_name"],
                "superkingdom": contaminant.get("superkingdom"),
                "min_reads": contaminant["min_reads"],
                "case_count": len(case_ids),
                "occurrences": occurrences,
            }
        )

    alerts.sort(key=lambda a: a["case_count"], reverse=True)

    result = {"alerts": alerts, "contaminant_case_ids": list(all_case_ids)}
    # Note: contaminant_case_ids contains MongoDB ObjectId strings, consistent
    # with the pathogen_cases endpoint, so the case list can use .has(c._id).
    _contaminant_alert_cache[window_days] = result
    return result


# ---------------------------------------------------------------------------
# NTC trends
# ---------------------------------------------------------------------------


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

    Taxa on the NTC ignorelist are excluded from all three chart datasets.
    """
    from datetime import date

    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    # Load ignorelist — excluded from all chart calculations
    ignore_docs = (
        await db["ntc_ignorelist"].find({}, {"taxon_id": 1}).to_list(length=1000)
    )
    ignored_ids: frozenset[int] = frozenset(d["taxon_id"] for d in ignore_docs)
    excluded_ids = HOST_TAXON_IDS | ignored_ids

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
            "kingdom_breakdown": [],
            "recurring_taxa": [],
        }

    total_ntcs = len(ntc_docs)
    min_case_count = max(1, round(total_ntcs * min_case_pct))

    # --- Build read_counts ---
    read_counts: list[dict] = []
    for doc in ntc_docs:
        kraken2_qc = (
            doc.get("taxprofiler", {}).get("classifiers", {}).get("kraken2", {})
        )
        classified = kraken2_qc.get("classified_reads")
        if classified is None:
            for p in doc.get("profiles", []):
                if p.get("classifier") == "kraken2":
                    classified = next(
                        (
                            int(e["abundance"])
                            for e in p.get("profile", [])
                            if e.get("taxon_id") == 1
                        ),
                        None,
                    )
                    break
        read_counts.append(
            {
                "sample_id": doc["sample_id"],
                "case_id": doc["case_id_str"],
                "order_date": doc.get("order_date"),
                "classified_reads": classified,
            }
        )

    # --- Build kingdom_breakdown (ignorelist applied) ---
    kingdom_breakdown: list[dict] = []
    for doc in ntc_docs:
        tally: dict[str, int] = {
            "Bacteria": 0,
            "Viruses": 0,
            "Eukaryota": 0,
            "Archaea": 0,
            "Other": 0,
        }
        for p in doc.get("profiles", []):
            if p.get("classifier") != "kraken2":
                continue
            for entry in p.get("profile", []):
                if entry.get("taxon_id") in excluded_ids:
                    continue
                sk = entry.get("superkingdom") or "Other"
                if sk not in tally:
                    sk = "Other"
                tally[sk] += int(entry.get("abundance", 0))
        kingdom_breakdown.append(
            {
                "sample_id": doc["sample_id"],
                "case_id": doc["case_id_str"],
                "order_date": doc.get("order_date"),
                **tally,
            }
        )

    # --- Build recurring_taxa (ignorelist applied) ---
    taxon_cases: dict[int, dict] = {}
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
            if taxon_id in excluded_ids:
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

    recurring_taxa: list[dict] = []
    for taxon in taxon_cases.values():
        distinct_cases = len({o["case_id"] for o in taxon["occurrences"]})
        if distinct_cases >= min_case_count:
            taxon["occurrences"].sort(key=lambda o: o["order_date"] or "")
            taxon["case_count"] = distinct_cases
            recurring_taxa.append(taxon)
    recurring_taxa.sort(key=lambda t: t["case_count"], reverse=True)

    return {
        "material": material,
        "window_days": window_days,
        "total_ntcs": total_ntcs,
        "min_case_count": min_case_count,
        "read_counts": read_counts,
        "kingdom_breakdown": kingdom_breakdown,
        "recurring_taxa": recurring_taxa,
    }
