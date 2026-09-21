# app/routers/ntc.py

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Literal, Optional

from app.audit import log_audit_event
from app.cache import get_cache_version, bump_cache_version
from app.database import get_db
from app.db_utils import fetch_capped
from app.auth.utils import get_current_user, require_role
from app.constants import HOST_TAXON_IDS, TAXON_ID_UNCLASSIFIED
from app.ntc_controls import (
    NtcControl,
    duplicated_analysis_ids,
    group_documents_by_control,
    pick_by_rank,
    resolve_controls,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ntc", tags=["ntc"])

# ---------------------------------------------------------------------------
# In-memory cache for contaminant alert results.
# key (window_days) → (db_version, result)
# ---------------------------------------------------------------------------

_contaminant_alert_cache: dict[int, tuple[int, dict]] = {}
_contaminant_alert_lock = asyncio.Lock()


def invalidate_contaminant_cache() -> None:
    _contaminant_alert_cache.clear()


# ---------------------------------------------------------------------------
# In-memory cache for NTC trends results.
# key → (db_version, timestamp, result)
# ---------------------------------------------------------------------------

_TRENDS_TTL = 900  # 15 minutes
_trends_cache: dict[tuple, tuple[int, float, dict]] = {}
_trends_lock = asyncio.Lock()


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
    docs = await fetch_capped(
        db["ntc_ignorelist"].find().sort("added_at", -1), "ntc_ignorelist"
    )
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
    await bump_cache_version(db)
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
    await bump_cache_version(db)
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
    docs = await fetch_capped(
        db["ntc_known_contaminants"].find().sort("added_at", -1),
        "ntc_known_contaminants",
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
    await bump_cache_version(db)
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
    await bump_cache_version(db)
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
    await bump_cache_version(db)
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
    current_version = await get_cache_version(db)
    if window_days in _contaminant_alert_cache:
        stored_version, cached_result = _contaminant_alert_cache[window_days]
        if stored_version == current_version:
            return cached_result

    async with _contaminant_alert_lock:
        # Re-check after acquiring lock: another coroutine may have computed
        # the result while we were waiting.
        current_version = await get_cache_version(db)
        if window_days in _contaminant_alert_cache:
            stored_version, cached_result = _contaminant_alert_cache[window_days]
            if stored_version == current_version:
                return cached_result

        contaminants = await fetch_capped(
            db["ntc_known_contaminants"].find(), "ntc_known_contaminants"
        )
        if not contaminants:
            result: dict = {"alerts": [], "contaminant_case_ids": []}
            _contaminant_alert_cache[window_days] = (current_version, result)
            return result

        from datetime import date

        cutoff = (date.today() - timedelta(days=window_days)).isoformat()

        # Build a lookup: taxon_id -> contaminant doc
        contaminant_map = {c["taxon_id"]: c for c in contaminants}

        # taxon_id -> list of affected NTC occurrences
        hits: dict[int, list[dict]] = {c["taxon_id"]: [] for c in contaminants}

        # Stream NTC sample docs so the full profile arrays are never all
        # resident at once. We iterate profiles in Python rather than using
        # $unwind because the NTC sample count is small and we need
        # per-contaminant min_reads thresholds.
        ntc_cursor = (
            db["samples"]
            .find(
                {
                    "sample_type": "negative_ctrl",
                    "order_date": {"$gte": cutoff},
                    # Superseded analyses must not contribute: their NTCs would
                    # double-count a re-sequenced case's contaminants.
                    "is_latest_analysis": True,
                },
                {
                    "sample_id": 1,
                    "case_id": 1,
                    "nucleic_acid": 1,
                    "order_date": 1,
                    "analysis_id": 1,
                    "ingested_at": 1,
                    "profiles": 1,
                },
            )
            .sort("order_date", -1)
        )

        async for doc in ntc_cursor:
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
                                "case_id": doc["case_id"],
                                "sample_id": doc["sample_id"],
                                "nucleic_acid": doc.get("nucleic_acid"),
                                "order_date": doc.get("order_date"),
                                "analysis_id": doc.get("analysis_id"),
                                "ingested_at": doc.get("ingested_at"),
                                "abundance": entry["abundance"],
                            }
                        )

        # A contaminated control is sequenced alongside every case in its run,
        # so one detection reached this loop as one hit per case: the taxon
        # read as several independent detections when it had been seen once.
        # The two counts answer different questions and both are kept —
        # control_count is how recurrent the contaminant is, case_count is how
        # many clinical results it puts in doubt.
        hit_groups = {
            tid: group_documents_by_control(taxon_hits)
            for tid, taxon_hits in hits.items()
            if taxon_hits
        }
        ambiguous_ids: set[str] = set()
        for control_groups in hit_groups.values():
            ambiguous_ids |= duplicated_analysis_ids(control_groups)
        version_by_analysis = (
            await _fetch_analysis_versions(db, ambiguous_ids) if ambiguous_ids else {}
        )

        alerts = []
        all_case_ids: set[str] = set()
        for contaminant in contaminants:
            tid = contaminant["taxon_id"]
            taxon_groups = hit_groups.get(tid)
            if not taxon_groups:
                continue
            controls = resolve_controls(taxon_groups, version_by_analysis)
            # Only the cases the taxon was actually detected in, which is what
            # makes a case suspect — not every case the control was run with.
            case_ids = {
                str(hit["case_id"]) for group in taxon_groups.values() for hit in group
            }
            all_case_ids.update(case_ids)
            alerts.append(
                {
                    "taxon_id": tid,
                    "taxon_name": contaminant["taxon_name"],
                    "superkingdom": contaminant.get("superkingdom"),
                    "min_reads": contaminant["min_reads"],
                    "control_count": len(controls),
                    "case_count": len(case_ids),
                    "occurrences": [
                        {
                            "sample_id": control.sample_id,
                            "case_ids": sorted(control.case_ids),
                            "order_date": control.order_date,
                            "abundance": control.winner["abundance"],
                        }
                        for control in sorted(
                            controls.values(),
                            key=lambda c: (c.order_date or "", c.sample_id),
                        )
                    ],
                }
            )

        # Recurrence first: a contaminant in five controls is systemic, where
        # one in a single control is one bad run however many cases it touched.
        alerts.sort(key=lambda a: (a["control_count"], a["case_count"]), reverse=True)

        result = {"alerts": alerts, "contaminant_case_ids": list(all_case_ids)}
        _contaminant_alert_cache[window_days] = (current_version, result)

    return result


# ---------------------------------------------------------------------------
# NTC trends
# ---------------------------------------------------------------------------


async def _fetch_analysis_versions(
    db: AsyncIOMotorDatabase, analysis_ids: set[str]
) -> dict[str, int]:
    """Map analysis id -> version for the given ids.

    Sample documents carry analysis_id but not the version, and the version is
    what decides which copy of a shared control came from the newest
    sequencing. Looked up only for controls that actually have several copies.
    """
    object_ids: list[ObjectId] = []
    for raw in analysis_ids:
        try:
            object_ids.append(ObjectId(raw))
        except (InvalidId, TypeError):
            # Not fatal — the control still resolves, just without this copy's
            # version to rank on — but it means a sample points at something
            # that is not an analysis, which should never happen.
            logger.warning("NTC sample carries an unusable analysis_id: %r", raw)
    if not object_ids:
        return {}

    docs = await (
        db["case_analysis"]
        .find({"_id": {"$in": object_ids}}, {"version": 1})
        .to_list(None)
    )
    return {str(doc["_id"]): doc.get("version") or 0 for doc in docs}


def _control_read_count(
    control: NtcControl,
    pipeline: str,
    profile_total_by_copy: dict[tuple[str, str], int],
) -> int | None:
    """Reads for a control, from the newest copy that reports them.

    Walks the ranking rather than reading the winner alone: a copy whose QC
    block is missing the count would otherwise plot the control as a gap even
    though an older run of the same control reported it.
    """
    for doc in control.copies:
        if pipeline == "trana":
            reads = (
                doc.get("trana", {})
                .get("nanoplot_processed", {})
                .get("number_of_reads")
            )
        else:
            reads = (
                doc.get("taxprofiler", {})
                .get("classifiers", {})
                .get("kraken2", {})
                .get("classified_reads")
            )
            if reads is None:
                reads = profile_total_by_copy.get(
                    (control.sample_id, str(doc.get("case_id") or ""))
                )
        if reads is not None:
            return reads
    return None


def _collapse_occurrences(
    occurrences: list[dict], controls: dict[tuple[str, str], NtcControl]
) -> list[dict]:
    """One occurrence per control, from the newest case that carries the taxon.

    The aggregation emits a row per (control, case), so a control shared by
    seven cases contributed seven identical points to the chart. The control's
    own order date is used rather than the row's, so the point sits exactly
    where the read-count and kingdom charts put that control.
    """
    by_sample: dict[str, dict[str, dict]] = {}
    for occurrence in occurrences:
        by_sample.setdefault(occurrence["sample_id"], {})[occurrence["case_id"]] = (
            occurrence
        )

    collapsed: list[dict] = []
    for control in controls.values():
        candidates = by_sample.get(control.sample_id)
        if not candidates:
            continue
        chosen = pick_by_rank(control, candidates)
        if chosen is None:
            continue
        collapsed.append(
            {
                "sample_id": control.sample_id,
                "case_ids": sorted(control.case_ids),
                "order_date": control.order_date,
                "abundance": chosen["abundance"],
            }
        )

    collapsed.sort(key=lambda o: (o["order_date"] or "", o["sample_id"]))
    return collapsed


async def _compute_ntc_trends(
    db: AsyncIOMotorDatabase,
    nucleic_acid: Literal["DNA", "RNA"],
    window_days: int,
    min_reads: float,
    min_control_pct: float,
    pipeline: Literal["taxprofiler", "trana"],
) -> dict:
    """Run the NTC trend aggregations and assemble the result dict."""
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    ignore_docs = await fetch_capped(
        db["ntc_ignorelist"].find({}, {"taxon_id": 1}), "ntc_ignorelist"
    )
    ignored_ids: frozenset[int] = frozenset(d["taxon_id"] for d in ignore_docs)
    excluded_ids: list[int] = list(HOST_TAXON_IDS | ignored_ids)

    base_query: dict = {
        "sample_type": "negative_ctrl",
        "nucleic_acid": nucleic_acid,
        "order_date": {"$gte": cutoff},
        # Latest analyses only, so a re-sequenced case contributes its newest
        # run and not one control document per run.
        "is_latest_analysis": True,
        # Scope to the requested pipeline. Only the classifier and the QC block
        # used to be pipeline-specific, so a trana control was counted in the
        # taxprofiler totals of the same nucleic acid. The two stats blocks are
        # mutually exclusive: the orchestrator writes whichever the bundle came
        # from and never both.
        ("trana" if pipeline == "trana" else "taxprofiler"): {"$exists": True},
    }

    # One control is sequenced alongside every case in its run, so it reaches
    # the database once per case. Collapse to physical controls before counting
    # anything: total_ntcs is shown to clinicians and sets the recurring-taxon
    # threshold, and counting documents inflated both — unevenly, by however
    # many cases each run happened to hold.
    rc_projection: dict = {
        "sample_id": 1,
        "case_id": 1,
        "nucleic_acid": 1,
        "order_date": 1,
        "analysis_id": 1,
        "ingested_at": 1,
    }
    if pipeline == "trana":
        rc_projection["trana.nanoplot_processed.number_of_reads"] = 1
    else:
        rc_projection["taxprofiler.classifiers.kraken2.classified_reads"] = 1

    ntc_docs = await db["samples"].find(base_query, rc_projection).to_list(None)
    groups = group_documents_by_control(ntc_docs)

    # Only a control with several copies needs its analyses ranked, so the
    # version lookup is skipped entirely when every control appears once.
    ambiguous_ids = duplicated_analysis_ids(groups)
    version_by_analysis = (
        await _fetch_analysis_versions(db, ambiguous_ids) if ambiguous_ids else {}
    )
    controls = resolve_controls(groups, version_by_analysis)
    total_ntcs = len(controls)

    if not total_ntcs:
        return {
            "nucleic_acid": nucleic_acid,
            "pipeline": pipeline,
            "window_days": window_days,
            "total_ntcs": 0,
            "read_counts": [],
            "kingdom_breakdown": [],
            "recurring_taxa": [],
        }

    min_control_count = max(1, round(total_ntcs * min_control_pct))

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
                    "case_id": "$case_id",
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

    # recurring_taxa: find taxa that appear in >= min_control_count distinct
    # controls. Deduplicate per (taxon_id, sample_id, case_id) first to avoid
    # double-counting taxa that appear at multiple ranks within the same sample.
    rt_pipeline: list[dict] = _unwind_profiles + [
        {"$match": {"profiles.profile.abundance": {"$gt": min_reads}}},
        # Deduplicate per (taxon, sample, case) — take max abundance.
        {
            "$group": {
                "_id": {
                    "taxon_id": "$profiles.profile.taxon_id",
                    "sample_id": "$sample_id",
                    "case_id": "$case_id",
                },
                "taxon_name": {"$first": "$profiles.profile.name"},
                "superkingdom": {"$first": "$profiles.profile.superkingdom"},
                "order_date": {"$first": "$order_date"},
                "abundance": {"$max": "$profiles.profile.abundance"},
            }
        },
        # Roll up per taxon: collect occurrences and count distinct controls.
        # Counting sample_ids rather than case_ids is what makes this
        # comparable to total_ntcs — a control shared by seven cases is one
        # control here, not seven. The count stays in Mongo so the threshold
        # still prunes before anything is transferred; the occurrences are
        # collapsed per control in Python, where the analysis ranking is known.
        {
            "$group": {
                "_id": "$_id.taxon_id",
                "taxon_name": {"$first": "$taxon_name"},
                "superkingdom": {"$first": "$superkingdom"},
                "distinct_controls": {"$addToSet": "$_id.sample_id"},
                "occurrences": {
                    "$push": {
                        "case_id": "$_id.case_id",
                        "sample_id": "$_id.sample_id",
                        "abundance": "$abundance",
                    }
                },
            }
        },
        {"$addFields": {"control_count": {"$size": "$distinct_controls"}}},
        {"$match": {"control_count": {"$gte": min_control_count}}},
        {"$sort": {"control_count": -1}},
    ]

    # Run both aggregations in parallel.
    # For taxprofiler, summing the profile provides a fallback for samples whose
    # QC data doesn't carry classified_reads directly. Taxpasta counts are
    # direct, so the root node is only the reads that could not be placed deeper
    # and is not the classified total — see app/taxonomy_utils.py.
    # For trana, reads come from nanoplot_processed; no profile fallback needed.
    if pipeline == "trana":
        kb_docs, rt_docs = await asyncio.gather(
            db["samples"].aggregate(kb_pipeline).to_list(None),
            db["samples"].aggregate(rt_pipeline).to_list(None),
        )
        profile_total_by_copy: dict[tuple[str, str], int] = {}
    else:
        # Every placed read: the whole profile except unclassified. The
        # ignorelist deliberately plays no part — this is what the classifier
        # produced, not the filtered view shown in the trends below.
        #
        # Grouped per (sample, case) rather than per sample: a control shared
        # by seven cases is seven documents carrying the same profile, and
        # summing across them multiplied the fallback read count by the number
        # of cases in the run.
        profile_total_pipeline: list[dict] = [
            {"$match": base_query},
            {"$unwind": "$profiles"},
            {"$match": {"profiles.classifier": "kraken2"}},
            {"$unwind": "$profiles.profile"},
            {"$match": {"profiles.profile.taxon_id": {"$ne": TAXON_ID_UNCLASSIFIED}}},
            {
                "$group": {
                    "_id": {"sample_id": "$sample_id", "case_id": "$case_id"},
                    "profile_total": {"$sum": "$profiles.profile.abundance"},
                }
            },
        ]
        kb_docs, rt_docs, profile_total_docs = await asyncio.gather(
            db["samples"].aggregate(kb_pipeline).to_list(None),
            db["samples"].aggregate(rt_pipeline).to_list(None),
            db["samples"].aggregate(profile_total_pipeline).to_list(None),
        )
        profile_total_by_copy = {
            (doc["_id"]["sample_id"], doc["_id"]["case_id"]): doc["profile_total"]
            for doc in profile_total_docs
        }

    # Controls in date order: one point per control on every chart, at the
    # control's own date.
    ordered_controls = sorted(
        controls.values(), key=lambda c: (c.order_date or "", c.sample_id)
    )

    # --- Assemble read_counts ---
    read_counts: list[dict] = [
        {
            "sample_id": control.sample_id,
            # Every case the control was sequenced alongside, for drill-down.
            # Was a single case_id, which is meaningless for a shared control.
            "case_ids": sorted(control.case_ids),
            "order_date": control.order_date,
            "classified_reads": _control_read_count(
                control, pipeline, profile_total_by_copy
            ),
        }
        for control in ordered_controls
    ]

    # --- Assemble kingdom_breakdown ---
    # Tallies arrive per (sample, case); serve the newest case's, so a control
    # reports one set of numbers rather than one per case that carried it.
    _known_kingdoms = frozenset(("Bacteria", "Viruses", "Eukaryota", "Archaea"))
    _kingdom_keys = ("Bacteria", "Viruses", "Eukaryota", "Archaea", "Other")
    # Keyed by sample_id alone: base_query pins one nucleic acid, so within a
    # single response that already identifies the control.
    tallies_by_sample: dict[str, dict[str, dict[str, int]]] = {}
    for doc in kb_docs:
        tally: dict[str, int] = dict.fromkeys(_kingdom_keys, 0)
        for kv in doc["kingdoms"]:
            sk = kv["k"] if kv["k"] in _known_kingdoms else "Other"
            tally[sk] += kv["v"]
        tallies_by_sample.setdefault(doc["_id"]["sample_id"], {})[
            doc["_id"]["case_id"]
        ] = tally

    kingdom_breakdown: list[dict] = []
    for control in ordered_controls:
        by_case = tallies_by_sample.get(control.sample_id, {})
        # Zeros when no copy had aggregatable entries: no kraken2 profile, an
        # empty profile, or every entry excluded. Distinguishing that from a
        # control that was never sequenced is the point of the entry.
        tally = pick_by_rank(control, by_case) or dict.fromkeys(_kingdom_keys, 0)
        kingdom_breakdown.append(
            {
                "sample_id": control.sample_id,
                "case_ids": sorted(control.case_ids),
                "order_date": control.order_date,
                **tally,
            }
        )

    # --- Assemble recurring_taxa ---
    recurring_taxa: list[dict] = [
        {
            "taxon_id": doc["_id"],
            "taxon_name": doc["taxon_name"],
            "superkingdom": doc["superkingdom"],
            "control_count": doc["control_count"],
            "occurrences": _collapse_occurrences(doc["occurrences"], controls),
        }
        for doc in rt_docs
    ]

    return {
        "nucleic_acid": nucleic_acid,
        "pipeline": pipeline,
        "window_days": window_days,
        "total_ntcs": total_ntcs,
        "min_control_count": min_control_count,
        "read_counts": read_counts,
        "kingdom_breakdown": kingdom_breakdown,
        "recurring_taxa": recurring_taxa,
    }


@router.get("/trends", summary="NTC contamination trends across cases")
async def get_ntc_trends(
    nucleic_acid: Literal["DNA", "RNA"] = Query(..., description="DNA or RNA"),
    window_days: int = Query(default=90, ge=7, le=365),
    min_reads: float = Query(default=3, gt=0),
    # Fraction of the window's physical controls, not of its cases: one
    # control is sequenced alongside every case in its run.
    min_control_pct: float = Query(default=0.10, ge=0.0, le=1.0),
    pipeline: Literal["taxprofiler", "trana"] = Query(default="taxprofiler"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    """
    Return NTC trend data for the given nucleic acid within a rolling window.

    Taxa on the NTC ignorelist are excluded from all three chart datasets.
    Uses MongoDB aggregation pipelines to avoid loading full profile arrays
    into Python memory.
    """
    cache_key = (nucleic_acid, window_days, min_reads, min_control_pct, pipeline)
    now = time.monotonic()
    current_version = await get_cache_version(db)
    cached = _trends_cache.get(cache_key)
    if cached is not None:
        stored_version, ts, cached_result = cached
        if stored_version == current_version and now - ts < _TRENDS_TTL:
            return cached_result

    async with _trends_lock:
        # Re-check after acquiring lock: another coroutine may have computed
        # the result while we were waiting.
        current_version = await get_cache_version(db)
        now = time.monotonic()
        cached = _trends_cache.get(cache_key)
        if cached is not None:
            stored_version, ts, cached_result = cached
            if stored_version == current_version and now - ts < _TRENDS_TTL:
                return cached_result

        result = await _compute_ntc_trends(
            db, nucleic_acid, window_days, min_reads, min_control_pct, pipeline
        )
        _trends_cache[cache_key] = (current_version, now, result)

    return result
