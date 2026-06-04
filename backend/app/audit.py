# app/audit.py

import logging
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

audit_logger = logging.getLogger("audit")


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

    Never raises — failures are caught and logged at WARNING so they never mask
    the actual HTTP response. The audit_log collection is append-only; documents
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

    try:
        await db["audit_log"].insert_one(doc.copy())
    except Exception:  # noqa: BLE001 — audit must never crash the caller (see docstring)
        logging.getLogger(__name__).warning(
            "Failed to write audit event to database",
            extra={"action": action, "actor": actor},
        )
