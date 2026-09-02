# app/ingestor/case_versioning.py
"""Case identity and analysis-version lifecycle for ingest.

A clinical case is sequenced one or more times. Ingesting an existing
``case_id`` appends a new ``case_analysis`` document rather than replacing the
case, so the version must be known before the prepare phase — blob keys are
namespaced per analysis version.
"""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


async def next_analysis_version(db: AsyncIOMotorDatabase, case_id: str) -> int:
    """Return the version the next analysis of ``case_id`` should carry.

    1 when the case has never been ingested. Two concurrent ingests of the same
    case can read the same value; the unique ``(case_id, version)`` index is
    what actually prevents a duplicate, failing the second commit rather than
    silently corrupting the family.
    """
    latest = await db["case_analysis"].find_one(
        {"case_id": case_id},
        sort=[("version", -1)],
        projection={"version": 1},
    )
    return int(latest["version"]) + 1 if latest else 1


async def assert_subject_matches(
    db: AsyncIOMotorDatabase,
    case_id: str,
    incoming_subject_id: Optional[str],
) -> None:
    """Fail when a bundle would attach to a case belonging to another subject.

    Re-using a case_id for a different patient is the one way this model can
    silently merge unrelated clinical data, so it is checked up front rather
    than left for a reviewer to notice. Runs before the prepare phase so the
    error arrives without waiting for a full parse.
    """
    case = await db["cases"].find_one({"case_id": case_id}, {"subject_id": 1})
    if case is None or case.get("subject_id") is None or incoming_subject_id is None:
        return

    subject = await db["subjects"].find_one(
        {"_id": case["subject_id"]}, {"subject_id": 1}
    )
    existing = subject.get("subject_id") if subject else None
    if existing is not None and existing != incoming_subject_id:
        raise ValueError(
            f"Case '{case_id}' belongs to subject '{existing}', but this bundle "
            f"is for subject '{incoming_subject_id}'. Every analysis of a case "
            f"must be for the same subject — use a different case_id."
        )


async def upsert_case_identity(
    db: AsyncIOMotorDatabase,
    identity: dict,
    subject_oid: Optional[ObjectId],
    now: datetime,
    session: Any,
) -> None:
    """Create the case on first ingest; refresh its mutable identity after.

    ``order_date``, ``created_at`` and the note thread are insert-only: the case
    keeps the date of the original order, and a re-sequencing must never reset
    the discussion. ``ticket_id`` and ``subject_id`` are refreshed only when the
    incoming bundle carries them, so a control-only re-run cannot blank out
    identity that the first run established.
    """
    set_on_insert: dict[str, Any] = {
        "case_id": identity["case_id"],
        "order_date": identity.get("order_date"),
        "created_at": now,
        "notes": [],
    }
    updates: dict[str, Any] = {}

    for field_name, value in (
        ("ticket_id", identity.get("ticket_id")),
        ("subject_id", subject_oid),
    ):
        if value is not None:
            updates[field_name] = value
        else:
            # Seed the field on insert so a first ingest without it still
            # produces a complete document, without overwriting a later run.
            set_on_insert[field_name] = None

    update: dict[str, Any] = {"$setOnInsert": set_on_insert}
    if updates:
        update["$set"] = updates

    await db["cases"].update_one(
        {"case_id": identity["case_id"]}, update, upsert=True, session=session
    )


async def demote_previous_analysis(
    db: AsyncIOMotorDatabase, case_id: str, session: Any
) -> None:
    """Clear ``is_latest`` on the case's current analysis and its samples.

    Must run *before* the new analysis is inserted. The partial unique index
    permits only one latest analysis per case, and MongoDB detects unique
    violations at write time rather than deferring them to commit — so
    insert-then-demote would succeed on a case's first ingest and fail on every
    re-sequencing.
    """
    previous = await db["case_analysis"].find_one_and_update(
        {"case_id": case_id, "is_latest": True},
        {"$set": {"is_latest": False}},
        projection={"_id": 1},
        session=session,
    )
    if previous is None:
        return

    await db["samples"].update_many(
        {"analysis_id": previous["_id"]},
        {"$set": {"is_latest_analysis": False}},
        session=session,
    )
