import logging

from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.audit import log_audit_event
from app.database import get_db
from app.models.sample import IngestRequest, TranaIngestRequest
from app.ingestor.orchestrator import ingest_case, ingest_trana_case
from app.routers import alerts, ntc
from app.auth.utils import require_role

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest")
async def ingest(
    request: IngestRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),
):
    try:
        result = await ingest_case(request, db)
        alerts._cache.clear()
        ntc.invalidate_contaminant_cache()
        ntc.invalidate_ntc_trends_cache()
        await log_audit_event(
            db,
            action="ingest",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="success",
        )
        return result
    except FileNotFoundError as e:
        logger.error("Ingest file not found: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "file_not_found"},
        )
        raise HTTPException(
            status_code=404, detail="One or more required input files were not found"
        )
    except ValueError as e:
        logger.error("Ingest validation error: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "validation_error"},
        )
        raise HTTPException(status_code=422, detail="Ingest data failed validation")
    except Exception as e:
        logger.error("Ingest failed with unexpected error: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "internal_error"},
        )
        raise HTTPException(
            status_code=500, detail="An internal error occurred during ingest"
        )


@router.post("/ingest/trana")
async def ingest_trana(
    request: TranaIngestRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),
):
    try:
        result = await ingest_trana_case(request, db)
        alerts._cache.clear()
        ntc.invalidate_contaminant_cache()
        ntc.invalidate_ntc_trends_cache()
        await log_audit_event(
            db,
            action="ingest_trana",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="success",
        )
        return result
    except FileNotFoundError as e:
        logger.error("Trana ingest file not found: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest_trana",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "file_not_found"},
        )
        raise HTTPException(
            status_code=404, detail="One or more required input files were not found"
        )
    except ValueError as e:
        logger.error("Trana ingest validation error: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest_trana",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "validation_error"},
        )
        raise HTTPException(status_code=422, detail="Ingest data failed validation")
    except Exception as e:
        logger.error("Trana ingest failed with unexpected error: %s", e, exc_info=True)
        await log_audit_event(
            db,
            action="ingest_trana",
            actor=_user["username"],
            resource_type="case",
            resource_id=request.case_id,
            outcome="failure",
            detail={"error": "internal_error"},
        )
        raise HTTPException(
            status_code=500, detail="An internal error occurred during ingest"
        )
