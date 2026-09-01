# app/routers/analyses.py
"""Run-scoped endpoints: samples, Krona, MultiQC, review and the report draft.

Every route here comes in two forms sharing one handler — a bare
``/cases/{case_id}/...`` that resolves to the case's latest analysis, and a
``/cases/{case_id}/analyses/{version}/...`` form addressing a specific run.
``version`` is a path parameter on the second and an optional query parameter
on the first, so the common path stays short while any run stays addressable.

Case identity and the note thread live in ``app.routers.cases``.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.audit import log_audit_event
from app.case_access import get_analysis_or_404, get_case_or_404
from app.auth.utils import get_current_user, require_role
from app.config import settings
from app.constants import HOST_TAXON_IDS
from app.database import get_client, get_db, maybe_transaction
from app.taxonomy_utils import host_pct_for, non_host_total

router = APIRouter(prefix="/cases", tags=["analyses"])


class ReviewPayload(BaseModel):
    notes: Optional[str] = None


class ReportSelectionsPayload(BaseModel):
    selections: dict[str, list[int]]


def _serialise_sample(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if doc.get("analysis_id") is not None:
        doc["analysis_id"] = str(doc["analysis_id"])
    if doc.get("subject_id"):
        doc["subject_id"] = str(doc["subject_id"])
    return doc


def _top_taxa_for(entries: list, clf_qc: Optional[dict] = None, n: int = 3) -> list:
    total = non_host_total(entries, clf_qc)
    non_host_entries = [
        e
        for e in entries
        if e.get("taxon_id") not in HOST_TAXON_IDS
        and e.get("name") != "unclassified"
        and not (e.get("name") or "").startswith("unclassified ")
    ]
    non_host_entries.sort(key=lambda e: e.get("abundance", 0), reverse=True)
    return [
        {
            "name": e["name"],
            "superkingdom": e.get("superkingdom"),
            "abundance": e["abundance"],
            "pct": round(e["abundance"] / total * 100, 3) if total else None,
        }
        for e in non_host_entries[:n]
    ]


def _spike_in_for(
    entries: list, spike_in_ids: set, clf_qc: Optional[dict] = None
) -> list:
    if not spike_in_ids:
        return []
    total = non_host_total(entries, clf_qc)
    return [
        {
            "name": e["name"],
            "taxon_id": e["taxon_id"],
            "abundance": e["abundance"],
            "pct": round(e["abundance"] / total * 100, 3) if total else None,
        }
        for e in entries
        if e.get("taxon_id") in spike_in_ids
    ]


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------


@router.get(
    "/{case_id}/analyses/{version}/samples", summary="List samples for one analysis"
)
@router.get("/{case_id}/samples", summary="List samples for a case's latest analysis")
async def list_samples_for_analysis(
    case_id: str,
    version: Optional[int] = None,
    type: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    analysis = await get_analysis_or_404(db, case_id, version)

    query: dict[str, Any] = {"analysis_id": analysis["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}
    elif type == "sample":
        query["sample_type"] = "sample"

    docs = await db["samples"].find(query).to_list(length=200)

    spike_in_ids = set(settings.controls_taxa.get("spike_in", []))

    result = []
    for doc in docs:
        top_taxa_by_clf = {}
        spike_in_by_clf = {}
        host_pct_by_clf = {}
        for p in doc.get("profiles", []):
            clf = p.get("classifier", "unknown")
            entries = p.get("profile", [])
            clf_qc = doc.get("taxprofiler", {}).get("classifiers", {}).get(clf)
            top_taxa_by_clf[clf] = _top_taxa_for(entries, clf_qc)
            spike_in_by_clf[clf] = _spike_in_for(entries, spike_in_ids, clf_qc)
            host_pct_by_clf[clf] = host_pct_for(entries, clf_qc)
        doc["top_taxa"] = top_taxa_by_clf
        doc["spike_in_taxa"] = spike_in_by_clf
        doc["host_pct"] = host_pct_by_clf
        doc.pop("profiles", None)
        result.append(_serialise_sample(doc))
    return result


# ---------------------------------------------------------------------------
# Blob-backed reports
# ---------------------------------------------------------------------------


@router.get("/{case_id}/analyses/{version}/krona", summary="Serve Krona HTML")
@router.get("/{case_id}/krona", summary="Serve Krona HTML for the latest analysis")
async def get_krona(
    case_id: str,
    version: Optional[int] = None,
    classifier: str = "kraken2",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    analysis = await get_analysis_or_404(db, case_id, version)

    from app.database import get_blob_store

    key = f"krona/{case_id}/v{analysis['version']}/{classifier}.html"
    html = await get_blob_store().get(key)
    if not html:
        raise HTTPException(
            status_code=404, detail=f"No Krona file for classifier '{classifier}'"
        )
    return HTMLResponse(content=html)


@router.get("/{case_id}/analyses/{version}/multiqc", summary="Serve MultiQC HTML")
@router.get("/{case_id}/multiqc", summary="Serve MultiQC HTML for the latest analysis")
async def get_multiqc(
    case_id: str,
    version: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    analysis = await get_analysis_or_404(db, case_id, version)

    from app.database import get_blob_store

    key = f"multiqc/{case_id}/v{analysis['version']}/report.html"
    html = await get_blob_store().get(key)
    if not html:
        raise HTTPException(
            status_code=404, detail="No MultiQC report for this analysis"
        )
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Review — per analysis. Reviewing v2 leaves v1's record untouched, so the
# list can honestly show which runs have been read.
# ---------------------------------------------------------------------------


@router.patch("/{case_id}/analyses/{version}/review", summary="Mark analysis reviewed")
@router.patch("/{case_id}/review", summary="Mark the latest analysis reviewed")
async def review_analysis(
    case_id: str,
    payload: ReviewPayload,
    version: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    analysis = await get_analysis_or_404(db, case_id, version)
    await db["case_analysis"].update_one(
        {"_id": analysis["_id"]},
        {
            "$set": {
                "review.reviewed": True,
                "review.reviewed_by": current_user["username"],
                "review.reviewed_at": datetime.now(timezone.utc),
                "review.notes": payload.notes,
            }
        },
    )
    await log_audit_event(
        db,
        action="review_case",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={
            "analysis_version": analysis["version"],
            "notes": payload.notes is not None,
        },
    )
    return {
        "case_id": case_id,
        "version": analysis["version"],
        "reviewed": True,
        "reviewed_by": current_user["username"],
    }


@router.delete("/{case_id}/analyses/{version}/review", summary="Remove analysis review")
@router.delete("/{case_id}/review", summary="Remove review from the latest analysis")
async def unreview_analysis(
    case_id: str,
    version: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    analysis = await get_analysis_or_404(db, case_id, version)
    await db["case_analysis"].update_one(
        {"_id": analysis["_id"]},
        {
            "$set": {
                "review.reviewed": False,
                "review.reviewed_by": None,
                "review.reviewed_at": None,
                "review.notes": None,
            }
        },
    )
    await log_audit_event(
        db,
        action="unreview_case",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={"analysis_version": analysis["version"]},
    )
    return {"case_id": case_id, "version": analysis["version"], "reviewed": False}


# ---------------------------------------------------------------------------
# Report draft
# ---------------------------------------------------------------------------


async def _valid_sample_ids(
    db: AsyncIOMotorDatabase, analysis_oid: ObjectId
) -> set[str]:
    """Human-readable sample_ids belonging to one analysis.

    The samples collection is authoritative — the analysis document does not
    carry a sample_ids array.
    """
    cursor = db["samples"].find({"analysis_id": analysis_oid}, {"sample_id": 1})
    return {doc["sample_id"] async for doc in cursor if "sample_id" in doc}


@router.patch(
    "/{case_id}/analyses/{version}/report",
    summary="Replace an analysis's per-sample report taxon selections",
    responses={
        404: {"description": "Case or analysis not found"},
        422: {"description": "Payload references sample_ids not in this analysis"},
    },
)
@router.patch("/{case_id}/report", summary="Replace the latest analysis's selections")
async def update_analysis_report(
    case_id: str,
    payload: ReportSelectionsPayload,
    version: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    analysis = await get_analysis_or_404(db, case_id, version)
    valid = await _valid_sample_ids(db, analysis["_id"])
    unknown = sorted(k for k in payload.selections if k not in valid)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown sample_id(s) for this analysis: {unknown}",
        )

    await db["case_analysis"].update_one(
        {"_id": analysis["_id"]},
        {"$set": {"report_selections": payload.selections}},
    )
    await log_audit_event(
        db,
        action="update_case_report",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={
            "analysis_version": analysis["version"],
            "samples": len(payload.selections),
            "taxa": sum(len(v) for v in payload.selections.values()),
        },
    )
    return {
        "case_id": case_id,
        "version": analysis["version"],
        "selections": payload.selections,
    }


@router.post(
    "/{case_id}/analyses/{version}/report/carry-forward",
    summary="Copy another analysis's report selections into this one",
    responses={404: {"description": "Case or analysis not found"}},
)
async def carry_forward_report(
    case_id: str,
    version: int,
    from_version: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    """Copy selections from an earlier analysis, dropping what no longer applies.

    Never automatic: a taxon picked against one run's data should not silently
    enter another run's report. Picks are kept only where both the sample and
    the taxon still exist in the target analysis, and everything dropped is
    reported back so the clinician can see what changed.
    """
    target = await get_analysis_or_404(db, case_id, version)
    source = await get_analysis_or_404(db, case_id, from_version)

    valid_samples = await _valid_sample_ids(db, target["_id"])
    taxa_by_sample: dict[str, set[int]] = {}
    async for doc in db["samples"].find(
        {"analysis_id": target["_id"]}, {"sample_id": 1, "all_taxon_ids": 1}
    ):
        taxa_by_sample[doc["sample_id"]] = set(doc.get("all_taxon_ids") or [])

    applied: dict[str, list[int]] = {}
    dropped: list[dict] = []
    for sample_id, taxon_ids in (source.get("report_selections") or {}).items():
        if sample_id not in valid_samples:
            dropped.append({"sample_id": sample_id, "reason": "sample not in analysis"})
            continue
        available = taxa_by_sample.get(sample_id, set())
        kept = [t for t in taxon_ids if t in available]
        missing = [t for t in taxon_ids if t not in available]
        if missing:
            dropped.append(
                {
                    "sample_id": sample_id,
                    "reason": "taxa not detected in this analysis",
                    "taxon_ids": missing,
                }
            )
        if kept:
            applied[sample_id] = kept

    await db["case_analysis"].update_one(
        {"_id": target["_id"]}, {"$set": {"report_selections": applied}}
    )
    await log_audit_event(
        db,
        action="carry_forward_case_report",
        actor=current_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={
            "from_version": from_version,
            "to_version": version,
            "samples": len(applied),
            "dropped": len(dropped),
        },
    )
    return {
        "case_id": case_id,
        "version": version,
        "from_version": from_version,
        "applied": applied,
        "dropped": dropped,
    }


# ---------------------------------------------------------------------------
# Deleting a single analysis
# ---------------------------------------------------------------------------


@router.delete(
    "/{case_id}/analyses/{version}",
    summary="Delete one analysis of a case",
    responses={
        404: {"description": "Case or analysis not found"},
        409: {"description": "Cannot delete a case's only analysis"},
    },
)
async def delete_analysis(
    case_id: str,
    version: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    """Remove one run, promoting the newest survivor to latest.

    Refuses to delete a case's only analysis: that would leave a case with no
    results, invisible in the list and impossible to reach. Deleting the case
    itself is the operation for that.
    """
    await get_case_or_404(db, case_id)
    analysis = await get_analysis_or_404(db, case_id, version)

    remaining = await db["case_analysis"].count_documents({"case_id": case_id})
    if remaining <= 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Analysis v{version} is the only analysis of case '{case_id}'. "
                f"Delete the case instead."
            ),
        )

    client = get_client()
    async with maybe_transaction(client) as session:
        await db["samples"].delete_many(
            {"analysis_id": analysis["_id"]}, session=session
        )
        await db["metaval_results"].delete_many(
            {"analysis_id": analysis["_id"]}, session=session
        )
        await db["case_analysis"].delete_one({"_id": analysis["_id"]}, session=session)

        # Promote the newest survivor when the deleted run was the latest, so
        # the case keeps exactly one latest analysis.
        if analysis.get("is_latest"):
            successor = await db["case_analysis"].find_one_and_update(
                {"case_id": case_id},
                {"$set": {"is_latest": True}},
                sort=[("version", -1)],
                session=session,
            )
            if successor is not None:
                await db["samples"].update_many(
                    {"analysis_id": successor["_id"]},
                    {"$set": {"is_latest_analysis": True}},
                    session=session,
                )

    from app.database import get_blob_store

    store = get_blob_store()
    for prefix in ("krona", "igv", "multiqc", "verification_data"):
        await store.delete_prefix(f"{prefix}/{case_id}/v{version}/")

    await log_audit_event(
        db,
        action="delete_case_analysis",
        actor=_user["username"],
        resource_type="case",
        resource_id=case_id,
        outcome="success",
        detail={"analysis_version": version},
    )
    return {"deleted": True, "case_id": case_id, "version": version}
