# app/case_access.py
"""Shared lookups over ``cases`` and ``case_analysis``.

A case holds clinical identity; each pipeline run of it is a ``case_analysis``
document. Routers need the same three things repeatedly — fetch the case, fetch
one analysis (usually the latest), and list the analyses for the version
switcher — so they live here rather than being duplicated across routers or
imported privately from one another.
"""

from typing import Any, Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings

# Fields backing AnalysisSummary. Deliberately excludes report_selections,
# sample_names, classifiers and the pipeline-info blocks: the list embeds one
# summary per superseded analysis, and those fields would grow the response
# with every run a case accumulates.
ANALYSIS_SUMMARY_PROJECTION: dict[str, Any] = {
    "_id": 0,
    "case_id": 1,
    "version": 1,
    "is_latest": 1,
    "order_date": 1,
    "ingested_at": 1,
    "analysis_type": 1,
    "sequencing_platform": 1,
    "review": 1,
    "sample_count": 1,
    "control_count": 1,
}


def serialise_case(doc: dict) -> dict:
    """Prepare a raw ``cases`` document for CaseResponse validation."""
    doc.pop("_id", None)
    if doc.get("subject_id") is not None:
        doc["subject_id"] = str(doc["subject_id"])
    ticket_id = doc.get("ticket_id")
    if ticket_id and settings.freshdesk_base_url:
        doc["ticket_url"] = settings.freshdesk_base_url.format(ticket_id=ticket_id)
    return doc


def serialise_analysis(doc: dict) -> dict:
    """Prepare a raw ``case_analysis`` document for response validation."""
    doc.pop("_id", None)
    return doc


async def get_case_or_404(db: AsyncIOMotorDatabase, case_id: str) -> dict:
    doc = await db["cases"].find_one({"case_id": case_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return doc


async def get_analysis_or_404(
    db: AsyncIOMotorDatabase, case_id: str, version: Optional[int] = None
) -> dict:
    """Return one analysis of a case — the latest when ``version`` is None.

    Callers that need the analysis's ``_id`` (to reach samples or metaval
    results) get it here; only the response serialisers drop it.
    """
    query: dict[str, Any] = {"case_id": case_id}
    if version is None:
        query["is_latest"] = True
    else:
        query["version"] = version

    doc = await db["case_analysis"].find_one(query)
    if not doc:
        detail = (
            f"Case '{case_id}' has no analyses"
            if version is None
            else f"Case '{case_id}' has no analysis v{version}"
        )
        raise HTTPException(status_code=404, detail=detail)
    return doc


async def list_analysis_summaries(db: AsyncIOMotorDatabase, case_id: str) -> list[dict]:
    """Every analysis of a case, newest first, as slim summaries."""
    return (
        await db["case_analysis"]
        .find({"case_id": case_id}, ANALYSIS_SUMMARY_PROJECTION)
        .sort("version", -1)
        .to_list(length=None)
    )
