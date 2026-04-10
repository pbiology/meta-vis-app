from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_db
from app.models.sample import IngestRequest
from app.ingestor.orchestrator import ingest_case
from app.routers import alerts, ntc
from app.auth.utils import require_role

router = APIRouter()


@router.post("/ingest")
async def ingest(
    request: IngestRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("writer", "admin")),  # ← add this line
):
    try:
        result = await ingest_case(request, db)
        alerts._cache.clear()
        ntc.invalidate_contaminant_cache()
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
