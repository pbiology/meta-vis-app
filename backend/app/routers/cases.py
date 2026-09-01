# app/routers/cases.py
"""Case identity, the case list, and the per-case note thread.

Everything scoped to a single pipeline run — samples, Krona, MultiQC, review
and the report draft — lives in ``app.routers.analyses`` instead.
"""

import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Annotated, Any, Optional

from app.audit import log_audit_event
from app.case_access import (
    ANALYSIS_SUMMARY_PROJECTION,
    get_analysis_or_404,
    get_case_or_404,
    list_analysis_summaries,
    serialise_analysis,
    serialise_case,
)
from app.config import settings
from app.database import get_client, get_db, maybe_transaction
from app.auth.utils import get_current_user, require_role
from app.models.case import CaseDetail, CaseListItem

router = APIRouter(prefix="/cases", tags=["cases"])

PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Fixed-path routes — must all appear before /{case_id} to avoid being
# swallowed by the parameterised route.
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Global case counts")
async def case_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Counts over latest analyses only.

    An analysis that was superseded before anyone reviewed it is work nobody
    will ever do, so counting it would inflate the pending queue permanently.
    Restricting every counter the same way also keeps
    ``total == pending + reviewed`` true. This affects the dashboard only: a
    superseded analysis still shows its own true status in the case list.
    """
    latest: dict[str, Any] = {"is_latest": True}
    analyses = db["case_analysis"]

    total = await analyses.count_documents(latest)
    pending = await analyses.count_documents(
        {**latest, "review.reviewed": {"$ne": True}}
    )
    reviewed = await analyses.count_documents({**latest, "review.reviewed": True})
    pending_shotgun = await analyses.count_documents(
        {**latest, "review.reviewed": {"$ne": True}, "analysis_type": "shotgun"}
    )
    pending_amplicon = await analyses.count_documents(
        {**latest, "review.reviewed": {"$ne": True}, "analysis_type": "amplicon"}
    )
    return {
        "total": total,
        "pending": pending,
        "reviewed": reviewed,
        "pending_shotgun": pending_shotgun,
        "pending_amplicon": pending_amplicon,
    }


@router.get(
    "/pathogen_cases",
    summary="Return IDs of cases that contain a known pathogen taxon",
)
async def pathogen_cases(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    pathogen_docs = await db["known_pathogens"].find({}, {"taxon_id": 1}).to_list(None)
    pathogen_ids = [d["taxon_id"] for d in pathogen_docs]
    if not pathogen_ids:
        return {"case_ids": []}

    # all_taxon_ids is a pre-computed flat array of taxon IDs stored on each
    # sample at ingest time, avoiding expensive $unwind on nested profile
    # arrays. Restricting to latest analyses keeps a superseded run from
    # flagging a case whose current results no longer show the pathogen.
    pipeline: list[dict] = [
        {
            "$match": {
                "all_taxon_ids": {"$in": pathogen_ids},
                "is_latest_analysis": True,
            }
        },
        {"$group": {"_id": "$case_id"}},
    ]
    results = await db["samples"].aggregate(pipeline).to_list(None)
    return {"case_ids": [r["_id"] for r in results]}


@router.get("", summary="List cases, one row per case")
async def list_cases(
    page: int = 1,
    search: Annotated[str, Query(max_length=128)] = "",
    reviewed: str | None = None,
    analysis_type: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """One row per clinical case, showing its latest analysis.

    Driven from ``case_analysis`` rather than ``cases``: the sort keys live on
    the analysis (``review.reviewed``, ``order_date``, ``ingested_at``), so
    sorting from the case side would straddle two collections and force an
    in-memory sort. Equality on the leading ``is_latest`` field followed by
    those keys is an index prefix, keeping the sort index-covered.
    """
    query: dict[str, Any] = {"is_latest": True}
    # case_id is denormalised onto the analysis, so search needs no join.
    if search.strip():
        query["case_id"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    if reviewed == "pending":
        query["review.reviewed"] = {"$ne": True}
    elif reviewed == "reviewed":
        query["review.reviewed"] = True
    if analysis_type in ("shotgun", "amplicon"):
        query["analysis_type"] = analysis_type

    # With no user filter the number of latest analyses is exactly the number
    # of cases, so the O(1) metadata count still applies.
    user_filtered = len(query) > 1
    total = (
        await db["case_analysis"].count_documents(query)
        if user_filtered
        else await db["cases"].estimated_document_count()
    )

    latest_docs = (
        await db["case_analysis"]
        .find(query, ANALYSIS_SUMMARY_PROJECTION)
        .sort([("review.reviewed", 1), ("order_date", -1), ("ingested_at", -1)])
        .skip((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .to_list(length=PAGE_SIZE)
    )

    case_ids = [d["case_id"] for d in latest_docs]
    cases_by_id = {
        c["case_id"]: c async for c in db["cases"].find({"case_id": {"$in": case_ids}})
    }
    superseded_by_case: dict[str, list[dict]] = {}
    async for doc in (
        db["case_analysis"]
        .find(
            {"case_id": {"$in": case_ids}, "is_latest": False},
            ANALYSIS_SUMMARY_PROJECTION,
        )
        .sort("version", -1)
    ):
        superseded_by_case.setdefault(doc["case_id"], []).append(doc)

    items = []
    for latest in latest_docs:
        case_doc = cases_by_id.get(latest["case_id"])
        if case_doc is None:
            # An analysis whose case was removed: skip rather than surface a
            # half-populated row into a clinical list.
            continue
        items.append(
            CaseListItem.model_validate(
                {
                    "case": serialise_case(case_doc),
                    "latest": latest,
                    "superseded_analyses": superseded_by_case.get(
                        latest["case_id"], []
                    ),
                }
            ).model_dump(mode="json")
        )

    return {
        "total": total,
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        "ticket_links_enabled": bool(settings.freshdesk_base_url),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Parameterised routes — /{case_id} and sub-routes
# ---------------------------------------------------------------------------


# Two paths, one handler: the bare form resolves to the latest analysis, the
# versioned form addresses a specific one. `version` is a path parameter on the
# second route and an unused query parameter on the first.
@router.get("/{case_id}/analyses/{version}", summary="Get a case at one analysis")
@router.get("/{case_id}", summary="Get a case with its latest analysis")
async def get_case(
    case_id: str,
    version: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    case_doc = await get_case_or_404(db, case_id)
    analysis = await get_analysis_or_404(db, case_id, version)
    summaries = await list_analysis_summaries(db, case_id)

    await log_audit_event(
        db,
        action="view_case",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={"analysis_version": analysis["version"]},
    )
    return CaseDetail.model_validate(
        {
            "case": serialise_case(case_doc),
            "analysis": serialise_analysis(analysis),
            "analyses": summaries,
        }
    ).model_dump(mode="json")


@router.delete("/{case_id}", summary="Delete a case and all associated data")
async def delete_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    case = await db["cases"].find_one({"case_id": case_id}, {"_id": 1, "subject_id": 1})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    subject_oid = case.get("subject_id")

    # Mongo state changes happen in a transaction so a mid-sequence failure
    # cannot leave orphan samples/metaval rows pointing at a deleted case.
    # Blob-store deletes run after commit: orphaned blobs are recoverable,
    # inconsistent Mongo state is not.
    client = get_client()
    async with maybe_transaction(client) as session:
        await db["samples"].delete_many({"case_id": case_id}, session=session)
        await db["metaval_results"].delete_many({"case_id": case_id}, session=session)
        await db["case_analysis"].delete_many({"case_id": case_id}, session=session)
        await db["cases"].delete_one({"_id": case["_id"]}, session=session)
        if subject_oid is not None:
            still_referenced = await db["cases"].find_one(
                {"subject_id": subject_oid}, {"_id": 1}, session=session
            )
            if not still_referenced:
                await db["subjects"].delete_one({"_id": subject_oid}, session=session)

    from app.database import get_blob_store

    # Every blob key is namespaced by case then analysis version
    # (`krona/{case_id}/v2/...`), so a per-case prefix still removes them all.
    store = get_blob_store()
    for prefix in ("krona", "igv", "multiqc", "verification_data"):
        await store.delete_prefix(f"{prefix}/{case_id}/")

    await log_audit_event(
        db,
        action="delete_case",
        actor=_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
    )
    return {"deleted": True, "case_id": case_id}


# ---------------------------------------------------------------------------
# Notes — attached to the case, not to an analysis, so a re-sequencing never
# strands the discussion on a superseded run.
# ---------------------------------------------------------------------------


class NotePayload(BaseModel):
    text: str


@router.post("/{case_id}/notes", summary="Add a note to a case")
async def add_note(
    case_id: str,
    payload: NotePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Note text cannot be empty")
    note = {
        "id": str(uuid.uuid4()),
        "text": payload.text.strip(),
        "author": current_user["username"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db["cases"].update_one(
        {"case_id": case_id},
        {"$push": {"notes": note}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    await log_audit_event(
        db,
        action="add_note",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
    )
    return note


@router.delete("/{case_id}/notes/{note_id}", summary="Delete a note from a case")
async def delete_note(
    case_id: str,
    note_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    case = await db["cases"].find_one({"case_id": case_id}, {"notes": 1})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    note = next((n for n in case.get("notes", []) if n.get("id") == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if (
        current_user["role"] != "admin"
        and note.get("author") != current_user["username"]
    ):
        raise HTTPException(
            status_code=403, detail="You can only delete your own notes"
        )

    await db["cases"].update_one(
        {"case_id": case_id},
        {"$pull": {"notes": {"id": note_id}}},
    )
    await log_audit_event(
        db,
        action="delete_note",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={"note_id": note_id},
    )
    return {"deleted": True}
