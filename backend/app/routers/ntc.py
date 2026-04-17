# app/routers/ntc.py

import asyncio
import time
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
# Simple in-memory cache for NTC trends results.
# Invalidated on ingest and on any change to the ignorelist.
# ---------------------------------------------------------------------------

_TRENDS_TTL = 900  # 15 minutes
_trends_cache: dict[tuple, tuple[float, dict]] = {}  # key -> (timestamp, payload)


def invalidate_ntc_trends_cache() -> None:
    _trends_cache.clear()


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
    # Ignoring a taxon affects trend calculations — invalidate caches
    invalidate_contaminant_cache()
    invalidate_ntc_trends_cache()
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
    invalidate_ntc_trends_cache()
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
    min_reads: float = Query(default=3, ge=0),
    min_case_pct: float = Query(default=0.10, ge=0.0, le=1.0),
    pipeline: Literal["taxprofiler", "trana"] = Query(default="taxprofiler"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    """
    Return NTC trend data for the given material type within a rolling window.

    Taxa on the NTC ignorelist are excluded from all three chart datasets.
    Uses MongoDB aggregation pipelines to avoid loading full profile arrays
    into Python memory.
    """
    from datetime import date

    cache_key = (material, window_days, min_reads, min_case_pct, pipeline)
    now = time.monotonic()
    cached = _trends_cache.get(cache_key)
    if cached is not None and now - cached[0] < _TRENDS_TTL:
        return cached[1]

    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    # Load ignorelist — excluded from all chart calculations
    ignore_docs = (
        await db["ntc_ignorelist"].find({}, {"taxon_id": 1}).to_list(length=1000)
    )
    ignored_ids: frozenset[int] = frozenset(d["taxon_id"] for d in ignore_docs)
    excluded_ids: list[int] = list(HOST_TAXON_IDS | ignored_ids)

    base_query: dict = {
        "sample_type": "negative_ctrl",
        "material": material,
        "order_date": {"$gte": cutoff},
    }

    total_ntcs: int = await db["samples"].count_documents(base_query)

    if not total_ntcs:
        result: dict = {
            "material": material,
            "pipeline": pipeline,
            "window_days": window_days,
            "total_ntcs": 0,
            "read_counts": [],
            "kingdom_breakdown": [],
            "recurring_taxa": [],
        }
        _trends_cache[cache_key] = (now, result)
        return result

    min_case_count = max(1, round(total_ntcs * min_case_pct))

    # --- Aggregation pipelines ---
    # Shared opening stages: match NTC samples, unwind to individual profile
    # entries for the selected classifier, and exclude ignored taxa — all inside
    # MongoDB so that full profile arrays are never transferred to Python.
    classifier = "emu" if pipeline == "trana" else "kraken2"
    _unwind_profiles: list[dict] = [
        {"$match": base_query},
        {"$unwind": "$profiles"},
        {"$match": {"profiles.classifier": classifier}},
        {"$unwind": "$profiles.profile"},
        {"$match": {"profiles.profile.taxon_id": {"$nin": excluded_ids}}},
    ]

    # kingdom_breakdown: sum abundances per (sample, superkingdom).
    # The superkingdom "Other" bucketing is done in Python after the aggregation
    # to avoid $cond/$in operators that some drivers/mocks don't support.
    kb_pipeline: list[dict] = _unwind_profiles + [
        {
            "$group": {
                "_id": {
                    "sample_id": "$sample_id",
                    "case_id": "$case_id_str",
                    "order_date": "$order_date",
                    "sk": "$profiles.profile.superkingdom",
                },
                "reads": {"$sum": "$profiles.profile.abundance"},
            }
        },
        {
            "$group": {
                "_id": {
                    "sample_id": "$_id.sample_id",
                    "case_id": "$_id.case_id",
                    "order_date": "$_id.order_date",
                },
                "kingdoms": {"$push": {"k": "$_id.sk", "v": "$reads"}},
            }
        },
    ]

    # recurring_taxa: find taxa that appear in >= min_case_count distinct cases.
    # Deduplicate per (taxon_id, sample_id, case_id) first to avoid double-counting
    # taxa that appear at multiple ranks within the same sample.
    rt_pipeline: list[dict] = _unwind_profiles + [
        {"$match": {"profiles.profile.abundance": {"$gt": min_reads}}},
        # Deduplicate per (taxon, sample, case) — take max abundance.
        {
            "$group": {
                "_id": {
                    "taxon_id": "$profiles.profile.taxon_id",
                    "sample_id": "$sample_id",
                    "case_id": "$case_id_str",
                },
                "taxon_name": {"$first": "$profiles.profile.name"},
                "superkingdom": {"$first": "$profiles.profile.superkingdom"},
                "order_date": {"$first": "$order_date"},
                "abundance": {"$max": "$profiles.profile.abundance"},
            }
        },
        # Roll up per taxon: collect occurrences and count distinct cases.
        {
            "$group": {
                "_id": "$_id.taxon_id",
                "taxon_name": {"$first": "$taxon_name"},
                "superkingdom": {"$first": "$superkingdom"},
                "distinct_cases": {"$addToSet": "$_id.case_id"},
                "occurrences": {
                    "$push": {
                        "case_id": "$_id.case_id",
                        "sample_id": "$_id.sample_id",
                        "order_date": "$order_date",
                        "abundance": "$abundance",
                    }
                },
            }
        },
        {"$addFields": {"case_count": {"$size": "$distinct_cases"}}},
        {"$match": {"case_count": {"$gte": min_case_count}}},
        {"$sort": {"case_count": -1}},
    ]

    # Run read_counts query and both aggregations in parallel.
    # For taxprofiler, a root-node aggregation (taxon_id == 1) provides a fallback
    # for samples whose QC data doesn't carry classified_reads directly.
    # For trana, reads come from nanoplot_processed; no root fallback needed.
    rc_projection: dict = {"sample_id": 1, "case_id_str": 1, "order_date": 1}
    if pipeline == "trana":
        rc_projection["trana.nanoplot_processed.number_of_reads"] = 1
    else:
        rc_projection["taxprofiler.classifiers.kraken2.classified_reads"] = 1

    rc_cursor = db["samples"].find(base_query, rc_projection).sort("order_date", 1)

    if pipeline == "trana":
        rc_docs, kb_docs, rt_docs = await asyncio.gather(
            rc_cursor.to_list(None),
            db["samples"].aggregate(kb_pipeline).to_list(None),
            db["samples"].aggregate(rt_pipeline).to_list(None),
        )
        root_by_sample: dict[str, int] = {}
    else:
        root_agg_pipeline: list[dict] = [
            {"$match": base_query},
            {"$unwind": "$profiles"},
            {"$match": {"profiles.classifier": "kraken2"}},
            {"$unwind": "$profiles.profile"},
            {"$match": {"profiles.profile.taxon_id": 1}},
            {
                "$group": {
                    "_id": "$sample_id",
                    "root_abundance": {"$first": "$profiles.profile.abundance"},
                }
            },
        ]
        rc_docs, kb_docs, rt_docs, root_docs = await asyncio.gather(
            rc_cursor.to_list(None),
            db["samples"].aggregate(kb_pipeline).to_list(None),
            db["samples"].aggregate(rt_pipeline).to_list(None),
            db["samples"].aggregate(root_agg_pipeline).to_list(None),
        )
        root_by_sample = {doc["_id"]: doc["root_abundance"] for doc in root_docs}

    # --- Assemble read_counts ---
    read_counts: list[dict] = []
    for doc in rc_docs:
        if pipeline == "trana":
            classified: int | None = (
                doc.get("trana", {})
                .get("nanoplot_processed", {})
                .get("number_of_reads")
            )
        else:
            classified = (
                doc.get("taxprofiler", {})
                .get("classifiers", {})
                .get("kraken2", {})
                .get("classified_reads")
            )
            if classified is None:
                classified = root_by_sample.get(doc["sample_id"])
        read_counts.append(
            {
                "sample_id": doc["sample_id"],
                "case_id": doc["case_id_str"],
                "order_date": doc.get("order_date"),
                "classified_reads": classified,
            }
        )

    # --- Assemble kingdom_breakdown ---
    _known_kingdoms = frozenset(("Bacteria", "Viruses", "Eukaryota", "Archaea"))
    _kingdom_keys = ("Bacteria", "Viruses", "Eukaryota", "Archaea", "Other")
    kingdom_breakdown: list[dict] = []
    for doc in kb_docs:
        tally: dict[str, int] = dict.fromkeys(_kingdom_keys, 0)
        for kv in doc["kingdoms"]:
            sk = kv["k"] if kv["k"] in _known_kingdoms else "Other"
            tally[sk] += kv["v"]
        kingdom_breakdown.append(
            {
                "sample_id": doc["_id"]["sample_id"],
                "case_id": doc["_id"]["case_id"],
                "order_date": doc["_id"]["order_date"],
                **tally,
            }
        )
    # Add all-zeros entries for NTC samples that had no aggregatable profile entries
    # (no kraken2 profile, empty profile, or every entry was excluded).
    kb_sample_ids: frozenset[str] = frozenset(
        entry["sample_id"] for entry in kingdom_breakdown
    )
    for doc in rc_docs:
        if doc["sample_id"] not in kb_sample_ids:
            kingdom_breakdown.append(
                {
                    "sample_id": doc["sample_id"],
                    "case_id": doc["case_id_str"],
                    "order_date": doc.get("order_date"),
                    **dict.fromkeys(_kingdom_keys, 0),
                }
            )

    kingdom_breakdown.sort(key=lambda d: d["order_date"] or "")

    # --- Assemble recurring_taxa ---
    recurring_taxa: list[dict] = [
        {
            "taxon_id": doc["_id"],
            "taxon_name": doc["taxon_name"],
            "superkingdom": doc["superkingdom"],
            "case_count": doc["case_count"],
            "occurrences": sorted(
                doc["occurrences"], key=lambda o: o["order_date"] or ""
            ),
        }
        for doc in rt_docs
    ]

    result = {
        "material": material,
        "pipeline": pipeline,
        "window_days": window_days,
        "total_ntcs": total_ntcs,
        "min_case_count": min_case_count,
        "read_counts": read_counts,
        "kingdom_breakdown": kingdom_breakdown,
        "recurring_taxa": recurring_taxa,
    }
    _trends_cache[cache_key] = (now, result)
    return result
