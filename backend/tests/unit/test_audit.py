# tests/unit/test_audit.py

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import audit
from app.audit import (
    audit_selftest,
    get_audit_insert_failures_total,
    log_audit_event,
)


@pytest.fixture(autouse=True)
def _reset_counter():
    audit._audit_insert_failures = 0
    yield
    audit._audit_insert_failures = 0


def _failing_db() -> MagicMock:
    """Build a mock db whose audit_log.insert_one raises RuntimeError."""
    collection = MagicMock()
    collection.insert_one = AsyncMock(side_effect=RuntimeError("mongo down"))
    db = MagicMock()
    db.__getitem__.return_value = collection
    return db


async def test_log_audit_event_writes_to_collection(fake_db):
    await log_audit_event(
        fake_db,
        action="view_case",
        actor="alice",
        resource_type="case",
        resource_id="C-001",
        outcome="success",
    )

    docs = await fake_db["audit_log"].find({}).to_list(None)
    assert len(docs) == 1
    assert docs[0]["action"] == "view_case"
    assert docs[0]["actor"] == "alice"
    assert docs[0]["resource_type"] == "case"
    assert docs[0]["resource_id"] == "C-001"
    assert docs[0]["outcome"] == "success"
    assert get_audit_insert_failures_total() == 0


async def test_log_audit_event_failure_increments_counter_and_logs_error(caplog):
    db = _failing_db()

    with caplog.at_level(logging.ERROR, logger="app.audit"):
        await log_audit_event(
            db,
            action="view_case",
            actor="alice",
            resource_type="case",
            resource_id="C-001",
            outcome="success",
        )

    assert get_audit_insert_failures_total() == 1
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].action == "view_case"
    assert errors[0].actor == "alice"
    assert errors[0].resource_type == "case"
    assert errors[0].resource_id == "C-001"
    assert errors[0].outcome == "success"
    assert errors[0].audit_insert_failures_total == 1
    assert errors[0].exc_info is not None


async def test_audit_selftest_success(fake_db, caplog):
    with caplog.at_level(logging.ERROR, logger="app.audit"):
        await audit_selftest(fake_db)

    assert get_audit_insert_failures_total() == 0
    assert not [r for r in caplog.records if r.levelno == logging.ERROR]
    docs = (
        await fake_db["audit_log"]
        .find({"action": "startup_audit_selftest"})
        .to_list(None)
    )
    assert len(docs) == 1
    assert docs[0]["actor"] == "system"
    assert docs[0]["resource_type"] == "system"


async def test_audit_selftest_failure_emits_loud_error(caplog):
    db = _failing_db()

    with caplog.at_level(logging.ERROR, logger="app.audit"):
        await audit_selftest(db)

    assert get_audit_insert_failures_total() == 1
    selftest_errors = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "self-test FAILED" in r.getMessage()
    ]
    assert len(selftest_errors) == 1
