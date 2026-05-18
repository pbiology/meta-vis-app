# app/routers/health.py

import logging
import time

from fastapi import APIRouter, Depends, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Collections reported by /health/ready. Fixed list (rather than listing the
# DB at request time) so the response shape is stable and the readiness check
# does not depend on indexed/un-indexed state of unknown collections.
_REPORTED_COLLECTIONS = (
    "cases",
    "samples",
    "users",
    "metaval_results",
    "taxa",
    "known_pathogens",
    "outbreak_ignorelist",
    "ntc_ignorelist",
    "ntc_known_contaminants",
)


class LivenessResponse(BaseModel):
    status: str


class DatabaseStatus(BaseModel):
    reachable: bool
    ping_ms: float | None = None


class ReadinessResponse(BaseModel):
    status: str
    database: DatabaseStatus
    collections: dict[str, int] = {}
    error: str | None = None


@router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe — process is up",
)
async def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe — DB reachable and basic stats",
)
async def ready(
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReadinessResponse:
    start = time.monotonic()
    try:
        await db.command("ping")
    except Exception as exc:
        logger.warning("Readiness probe failed: DB ping error: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unavailable",
            database=DatabaseStatus(reachable=False),
            error=f"database ping failed: {exc}",
        )
    ping_ms = round((time.monotonic() - start) * 1000, 2)

    counts: dict[str, int] = {}
    try:
        for name in _REPORTED_COLLECTIONS:
            counts[name] = await db[name].estimated_document_count()
    except Exception as exc:
        logger.warning("Readiness probe failed: collection count error: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unavailable",
            database=DatabaseStatus(reachable=True, ping_ms=ping_ms),
            error=f"collection count failed: {exc}",
        )

    return ReadinessResponse(
        status="ok",
        database=DatabaseStatus(reachable=True, ping_ms=ping_ms),
        collections=counts,
    )
