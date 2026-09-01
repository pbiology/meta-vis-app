# tests/helpers.py
# Importable test helpers — shared across integration test files.
# (conftest.py cannot be imported directly as a module.)

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from unittest.mock import patch

from bson import ObjectId
from fastapi import APIRouter, FastAPI

from app.database import get_db
from app.auth.utils import get_current_user, require_role


class FakeBlobStore:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def put(self, key: str, value: str):
        self._store[key] = value

    async def delete_prefix(self, prefix: str):
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]


def make_user(
    role: str = "admin",
    username: str = "testuser",
    sub: str | None = None,
) -> dict:
    return {"sub": sub or f"sub-{username}", "username": username, "role": role}


def override_auth(app: FastAPI, role: str = "admin", username: str = "testuser"):
    u = make_user(role, username)
    app.dependency_overrides[get_current_user] = lambda: u
    for r in ("reader", "writer", "admin"):
        app.dependency_overrides[require_role(r)] = lambda u=u: u
    app.dependency_overrides[require_role("writer", "admin")] = lambda u=u: u


def make_test_app(
    router: "APIRouter | Sequence[APIRouter]",
    fake_db,
    fake_blob,
    role: str = "admin",
):
    """Build a test app from one router or several.

    Case endpoints span two routers (``cases`` for identity and notes,
    ``analyses`` for run-scoped resources), so tests covering both pass a list.
    """
    application = FastAPI()
    routers: Iterable[APIRouter] = [router] if isinstance(router, APIRouter) else router
    for r in routers:
        application.include_router(r, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: fake_db
    override_auth(application, role)
    patch("app.database.get_blob_store", return_value=fake_blob).start()
    return application


# ---------------------------------------------------------------------------
# Seeding — a case and its analyses are two documents, and samples hang off
# the analysis, so tests seed through these rather than inserting by hand.
# ---------------------------------------------------------------------------


def make_review(reviewed: bool = False, reviewed_by: str | None = "alice") -> dict:
    return {
        "reviewed": reviewed,
        "reviewed_by": reviewed_by if reviewed else None,
        "reviewed_at": None,
        "notes": None,
    }


async def insert_case(
    db,
    case_id: str = "testcase",
    *,
    reviewed: bool = False,
    order_date: str | None = "2026-01-01",
    analysis_type: str | None = None,
    subject_id: Any = None,
    ticket_id: str | None = None,
    version: int = 1,
    is_latest: bool = True,
    reviewed_by: str | None = "alice",
    **analysis_fields: Any,
) -> ObjectId:
    """Seed a case and one analysis of it; returns the analysis ``_id``.

    Call again with the same ``case_id`` and a higher ``version`` to add a
    re-sequencing. The caller is responsible for demoting the previous analysis
    when it wants a realistic family, mirroring what ingest does.
    """
    await db["cases"].update_one(
        {"case_id": case_id},
        {
            "$setOnInsert": {
                "case_id": case_id,
                "order_date": order_date,
                "subject_id": subject_id,
                "ticket_id": ticket_id,
                "notes": [],
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    analysis: dict[str, Any] = {
        "_id": ObjectId(),
        "case_id": case_id,
        "version": version,
        "is_latest": is_latest,
        "order_date": order_date,
        "ingested_at": datetime.now(timezone.utc),
        "analysis_type": analysis_type,
        "sequencing_platform": None,
        "classifiers": [],
        "has_krona": False,
        "has_multiqc": False,
        "pipeline_info": None,
        "sample_count": 0,
        "control_count": 0,
        "sample_names": [],
        "report_selections": {},
        "review": make_review(reviewed, reviewed_by),
    }
    analysis.update(analysis_fields)
    await db["case_analysis"].insert_one(analysis)
    return analysis["_id"]


async def insert_sample(
    db,
    analysis_id: ObjectId,
    case_id: str = "testcase",
    sample_id: str = "S1",
    *,
    sample_type: str = "sample",
    material: str = "DNA",
    order_date: str | None = "2026-01-01",
    is_latest_analysis: bool = True,
    **fields: Any,
) -> ObjectId:
    """Seed one sample belonging to ``analysis_id``."""
    doc: dict[str, Any] = {
        "_id": ObjectId(),
        "analysis_id": analysis_id,
        "case_id": case_id,
        "is_latest_analysis": is_latest_analysis,
        "sample_id": sample_id,
        "sample_type": sample_type,
        "material": material,
        "order_date": order_date,
        "profiles": [],
        "review": make_review(),
        "ingested_at": datetime.now(timezone.utc),
    }
    doc.update(fields)
    await db["samples"].insert_one(doc)
    return doc["_id"]
