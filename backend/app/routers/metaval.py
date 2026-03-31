# app/routers/metaval.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/metaval", tags=["metaval"])


def _oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid id: '{id_str}'")


def _serialise(doc: dict) -> dict:
    doc["_id"]       = str(doc["_id"])
    doc["case_id"]   = str(doc["case_id"])
    if doc.get("sample_id"):
        doc["sample_id"] = str(doc["sample_id"])
    # Strip igv_html from organism list — returned separately
    for org in doc.get("organisms", []):
        org.pop("igv_html", None)
    return doc


@router.get("/sample/{sample_id}", summary="List metaval results for a sample")
async def list_metaval_for_sample(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = await db["metaval_results"].find(
        {"sample_id": _oid(sample_id)}
    ).to_list(length=200)
    return [_serialise(d) for d in docs]


@router.get("/{metaval_id}", summary="Get a single metaval result with IGV html stripped")
async def get_metaval(
    metaval_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["metaval_results"].find_one({"_id": _oid(metaval_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Metaval result not found")
    return _serialise(doc)


@router.get("/{metaval_id}/igv/{organism_name}", summary="Serve IGV HTML for a specific organism")
async def get_igv(
    metaval_id: str,
    organism_name: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["metaval_results"].find_one({"_id": _oid(metaval_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Metaval result not found")

    org = next((o for o in doc.get("organisms", []) if o["organism_name"] == organism_name), None)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organism '{organism_name}' not found")
    if org.get("igv_too_large"):
        raise HTTPException(status_code=413, detail="IGV file exceeds 10 MB limit")
    if not org.get("igv_html"):
        raise HTTPException(status_code=404, detail="IGV HTML not available")

    return HTMLResponse(content=org["igv_html"])