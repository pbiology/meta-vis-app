import logging
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Header, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError

from app.audit import log_audit_event
from app.auth.utils import require_role
from app.cache import bump_cache_version
from app.config import settings
from app.database import get_db
from app.ingestor.loader import (
    BundleError,
    BundleTooLargeError,
    load_taxprofiler_bundle,
    load_trana_bundle,
)
from app.ingestor.orchestrator import ingest_case, ingest_trana_case
from app.routers import alerts, ntc

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_content_length(declared_content_length: int | None) -> None:
    """Reject obviously oversized uploads before reading the body."""
    cap = settings.ingest_upload_max_compressed_bytes
    if declared_content_length is not None and declared_content_length > cap:
        raise BundleTooLargeError(
            f"Bundle exceeds compressed cap of {cap} bytes "
            f"(Content-Length={declared_content_length})"
        )


async def _record_audit_event(
    db: AsyncIOMotorDatabase,
    action: str,
    actor: str,
    case_id: str | None,
    outcome: str,
    detail: dict | None = None,
) -> None:
    await log_audit_event(
        db,
        action=action,
        actor=actor,
        resource_type="case",
        resource_id=case_id or "(unknown)",
        outcome=outcome,
        detail=detail,
    )


async def _invalidate_caches(db: AsyncIOMotorDatabase) -> None:
    alerts._cache.clear()
    ntc.invalidate_contaminant_cache()
    ntc.invalidate_ntc_trends_cache()
    await bump_cache_version(db)


@router.post("/ingest/taxprofiler")
async def ingest_taxprofiler(
    bundle: UploadFile = File(...),
    content_length: int | None = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(require_role("writer", "admin")),
):
    """Upload a tar.gz bundle and ingest one taxprofiler case.

    The bundle layout is documented in :mod:`app.ingestor.loader`. The server
    streams the upload to a TemporaryDirectory, hands it to the loader, then
    to the orchestrator. The tempdir (and all extracted files) are cleaned up
    when this handler returns, success or failure.
    """
    case_id: str | None = None
    with tempfile.TemporaryDirectory(prefix="ingest_") as tmp:
        extract_dir = Path(tmp)

        try:
            _check_content_length(content_length)
            # Stream the upload directly into the loader — no intermediate
            # "bundle.tar" staged on disk. FastAPI's UploadFile.file is a
            # SpooledTemporaryFile already, so we just hand it to tarfile in
            # streaming mode.
            t0 = time.perf_counter()
            meta, inputs = await load_taxprofiler_bundle(bundle.file, extract_dir)
            t_extract = time.perf_counter()
            case_id = meta.case_id
            result = await ingest_case(meta, inputs, db)
            t_ingest = time.perf_counter()
            logger.info(
                "ingest timings case=%s extract_ms=%d ingest_ms=%d total_ms=%d",
                case_id,
                int((t_extract - t0) * 1000),
                int((t_ingest - t_extract) * 1000),
                int((t_ingest - t0) * 1000),
            )
        except BundleTooLargeError as e:
            logger.warning("Ingest bundle too large: %s", e)
            await _record_audit_event(
                db,
                "ingest",
                user["username"],
                case_id,
                "failure",
                {"error": "bundle_too_large"},
            )
            raise HTTPException(status_code=413, detail=str(e))
        except BundleError as e:
            logger.warning("Ingest bundle malformed: %s", e)
            await _record_audit_event(
                db,
                "ingest",
                user["username"],
                case_id,
                "failure",
                {"error": "bundle_malformed"},
            )
            raise HTTPException(status_code=400, detail=str(e))
        except ValidationError as e:
            logger.warning("Ingest manifest validation error: %s", e)
            await _record_audit_event(
                db,
                "ingest",
                user["username"],
                case_id,
                "failure",
                {"error": "manifest_validation_error"},
            )
            raise HTTPException(
                status_code=422, detail=f"Manifest validation failed: {e.errors()}"
            )
        except ValueError as e:
            logger.error("Ingest validation error: %s", e, exc_info=True)
            await _record_audit_event(
                db,
                "ingest",
                user["username"],
                case_id,
                "failure",
                {"error": "validation_error"},
            )
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("Ingest failed with unexpected error: %s", e, exc_info=True)
            await _record_audit_event(
                db,
                "ingest",
                user["username"],
                case_id,
                "failure",
                {"error": "internal_error"},
            )
            raise HTTPException(
                status_code=500, detail="An internal error occurred during ingest"
            )

        await _invalidate_caches(db)
        await _record_audit_event(db, "ingest", user["username"], case_id, "success")
        return result


@router.post("/ingest/trana")
async def ingest_trana(
    bundle: UploadFile = File(...),
    content_length: int | None = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(require_role("writer", "admin")),
):
    """Upload a tar.gz bundle and ingest one Trana (Emu/ONT) case."""
    case_id: str | None = None
    with tempfile.TemporaryDirectory(prefix="ingest_trana_") as tmp:
        extract_dir = Path(tmp)

        try:
            _check_content_length(content_length)
            meta, inputs = await load_trana_bundle(bundle.file, extract_dir)
            case_id = meta.case_id
            result = await ingest_trana_case(meta, inputs, db)
        except BundleTooLargeError as e:
            logger.warning("Trana ingest bundle too large: %s", e)
            await _record_audit_event(
                db,
                "ingest_trana",
                user["username"],
                case_id,
                "failure",
                {"error": "bundle_too_large"},
            )
            raise HTTPException(status_code=413, detail=str(e))
        except BundleError as e:
            logger.warning("Trana ingest bundle malformed: %s", e)
            await _record_audit_event(
                db,
                "ingest_trana",
                user["username"],
                case_id,
                "failure",
                {"error": "bundle_malformed"},
            )
            raise HTTPException(status_code=400, detail=str(e))
        except ValidationError as e:
            logger.warning("Trana ingest manifest validation error: %s", e)
            await _record_audit_event(
                db,
                "ingest_trana",
                user["username"],
                case_id,
                "failure",
                {"error": "manifest_validation_error"},
            )
            raise HTTPException(
                status_code=422, detail=f"Manifest validation failed: {e.errors()}"
            )
        except ValueError as e:
            logger.error("Trana ingest validation error: %s", e, exc_info=True)
            await _record_audit_event(
                db,
                "ingest_trana",
                user["username"],
                case_id,
                "failure",
                {"error": "validation_error"},
            )
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("Trana ingest failed: %s", e, exc_info=True)
            await _record_audit_event(
                db,
                "ingest_trana",
                user["username"],
                case_id,
                "failure",
                {"error": "internal_error"},
            )
            raise HTTPException(
                status_code=500, detail="An internal error occurred during ingest"
            )

        await _invalidate_caches(db)
        await _record_audit_event(
            db, "ingest_trana", user["username"], case_id, "success"
        )
        return result
