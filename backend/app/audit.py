# app/audit.py

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

audit_logger = logging.getLogger("audit")
logger = logging.getLogger(__name__)

# In-process counter of failed audit_log inserts. Exposed via
# get_audit_insert_failures_total() so CLAUDE_TODO #22 (observability) can
# register it with a real metrics registry without touching call sites.
_audit_insert_failures = 0


def get_audit_insert_failures_total() -> int:
    """Return the running count of failed audit_log inserts since process start."""
    return _audit_insert_failures


async def log_audit_event(
    db: AsyncIOMotorDatabase,
    *,
    action: str,
    actor: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    detail: Optional[dict] = None,
) -> None:
    """
    Emit a structured audit event to both the logger and the audit_log collection.

    Never raises — failures are caught, logged at ERROR with exc_info, and
    counted in `get_audit_insert_failures_total()` so they never mask the
    actual HTTP response. The audit_log collection is append-only; documents
    are never modified after insertion.

    Args:
        db: The Motor database instance.
        action: Verb-noun action name, e.g. "review_case", "login_failed".
        actor: Username of the user performing the action.
        resource_type: Entity type, e.g. "case", "user", "ignorelist_entry".
        resource_id: Natural key of the affected resource as a string.
        outcome: "success" or "failure".
        detail: Optional dict of action-specific metadata (no passwords or PHI).
    """
    doc = {
        "timestamp": datetime.now(timezone.utc),
        "action": action,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "detail": detail,
    }

    audit_logger.info(
        action,
        extra={k: v for k, v in doc.items() if k != "timestamp"},
    )

    global _audit_insert_failures
    try:
        await db["audit_log"].insert_one(doc.copy())
    except Exception:  # noqa: BLE001 — audit must never crash the caller (see docstring)
        _audit_insert_failures += 1
        logger.error(
            "Failed to write audit event to database",
            extra={
                "action": action,
                "actor": actor,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
                "audit_insert_failures_total": _audit_insert_failures,
            },
            exc_info=True,
        )


async def audit_selftest(db: AsyncIOMotorDatabase) -> None:
    """
    Write a sentinel audit event on boot to verify the audit pipeline works.

    Called from `connect_db()` after indexes are created. Does not raise —
    a failure is reported via a loud ERROR log line and the failure counter,
    matching the never-break-the-caller contract of log_audit_event.
    """
    before = get_audit_insert_failures_total()
    await log_audit_event(
        db,
        action="startup_audit_selftest",
        actor="system",
        resource_type="system",
        resource_id=f"pid:{os.getpid()}",
        outcome="success",
    )
    if get_audit_insert_failures_total() > before:
        logger.error(
            "Audit self-test FAILED — audit writes are not landing in MongoDB. "
            "Clinical audit trail is unreliable until this is fixed."
        )
