import logging
import tempfile
import time
from pathlib import Path
from typing import Annotated, Any, Awaitable, Callable

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
from app.ingestor.orchestrator import ingest_taxprofiler_case, ingest_trana_case
from app.routers import alerts, ntc

router = APIRouter()
logger = logging.getLogger(__name__)


# Shared OpenAPI response declarations for the two ingest endpoints. Keeps the
# schema accurate (every HTTPException status code in the handler appears here)
# and saves duplicating the dict on each route.
_INGEST_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Bundle is malformed (bad tar, manifest/bundle mismatch)"},
    413: {"description": "Bundle exceeds configured size cap"},
    422: {"description": "Manifest validation failed or business-rule rejection"},
    500: {"description": "Unexpected error during ingest"},
}


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


# Type for the closure that runs the actual ingest. Takes a path to a tempdir
# and returns (case_id, result_dict). Raises BundleError / BundleTooLargeError
# / ValidationError / ValueError / Exception as appropriate.
_RunIngest = Callable[[Path], Awaitable[tuple[str, dict]]]


async def _run_with_error_handling(
    *,
    action: str,
    tmp_prefix: str,
    db: AsyncIOMotorDatabase,
    username: str,
    content_length: int | None,
    run: _RunIngest,
) -> dict:
    """Drive one ingest request: tempdir lifecycle, content-length check,
    structured error mapping, audit logging, cache invalidation.

    The two ingest endpoints differ only in which loader/orchestrator they
    use; both share this exact error ladder. Keeping it in one place ensures
    the audit + HTTP behaviour stay consistent between taxprofiler and trana.
    """
    case_id: str | None = None
    with tempfile.TemporaryDirectory(prefix=tmp_prefix) as tmp:
        extract_dir = Path(tmp)
        try:
            _check_content_length(content_length)
            case_id, result = await run(extract_dir)
        except BundleTooLargeError as e:
            logger.warning("%s bundle too large: %s", action, e)
            await _record_audit_event(
                db,
                action,
                username,
                case_id,
                "failure",
                {"error": "bundle_too_large"},
            )
            raise HTTPException(status_code=413, detail=str(e)) from e
        except BundleError as e:
            logger.warning("%s bundle malformed: %s", action, e)
            await _record_audit_event(
                db,
                action,
                username,
                case_id,
                "failure",
                {"error": "bundle_malformed"},
            )
            raise HTTPException(status_code=400, detail=str(e)) from e
        except ValidationError as e:
            logger.warning("%s manifest validation error: %s", action, e)
            await _record_audit_event(
                db,
                action,
                username,
                case_id,
                "failure",
                {"error": "manifest_validation_error"},
            )
            raise HTTPException(
                status_code=422,
                detail=f"Manifest validation failed: {e.errors()}",
            ) from e
        except ValueError as e:
            logger.exception("%s validation error", action)
            await _record_audit_event(
                db,
                action,
                username,
                case_id,
                "failure",
                {"error": "validation_error"},
            )
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:
            logger.exception("%s failed with unexpected error", action)
            await _record_audit_event(
                db,
                action,
                username,
                case_id,
                "failure",
                {"error": "internal_error"},
            )
            raise HTTPException(
                status_code=500,
                detail="An internal error occurred during ingest",
            ) from e

        await _invalidate_caches(db)
        await _record_audit_event(db, action, username, case_id, "success")
        return result


@router.post("/ingest/taxprofiler", responses=_INGEST_RESPONSES)
async def ingest_taxprofiler(
    bundle: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(require_role("writer", "admin"))],
    content_length: Annotated[int | None, Header()] = None,
) -> dict:
    """Upload a tar.gz bundle and ingest one taxprofiler case.

    The bundle layout is documented in :mod:`app.ingestor.loader`. The server
    streams the upload to a TemporaryDirectory, hands it to the loader, then
    to the orchestrator. The tempdir (and all extracted files) are cleaned up
    when this handler returns, success or failure.
    """

    async def run(extract_dir: Path) -> tuple[str, dict]:
        t0 = time.perf_counter()
        meta, inputs = await load_taxprofiler_bundle(bundle.file, extract_dir)
        t_extract = time.perf_counter()
        result = await ingest_taxprofiler_case(meta, inputs, db)
        t_ingest = time.perf_counter()
        logger.info(
            "ingest timings case=%s extract_ms=%d ingest_ms=%d total_ms=%d",
            meta.case_id,
            int((t_extract - t0) * 1000),
            int((t_ingest - t_extract) * 1000),
            int((t_ingest - t0) * 1000),
        )
        return meta.case_id, result

    return await _run_with_error_handling(
        action="ingest",
        tmp_prefix="ingest_",
        db=db,
        username=user["username"],
        content_length=content_length,
        run=run,
    )


@router.post("/ingest/trana", responses=_INGEST_RESPONSES)
async def ingest_trana(
    bundle: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(require_role("writer", "admin"))],
    content_length: Annotated[int | None, Header()] = None,
) -> dict:
    """Upload a tar.gz bundle and ingest one Trana (Emu/ONT) case."""

    async def run(extract_dir: Path) -> tuple[str, dict]:
        meta, inputs = await load_trana_bundle(bundle.file, extract_dir)
        result = await ingest_trana_case(meta, inputs, db)
        return meta.case_id, result

    return await _run_with_error_handling(
        action="ingest_trana",
        tmp_prefix="ingest_trana_",
        db=db,
        username=user["username"],
        content_length=content_length,
        run=run,
    )
