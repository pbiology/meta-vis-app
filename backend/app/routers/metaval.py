# app/routers/metaval.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
import asyncio
import requests as http_requests
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
    doc["_id"] = str(doc["_id"])
    doc["case_id"] = str(doc["case_id"])
    if doc.get("sample_id"):
        doc["sample_id"] = str(doc["sample_id"])
    # Strip internal storage fields from organism list
    for org in doc.get("organisms", []):
        org.pop("igv_html", None)
        org.pop("igv_key", None)
    # Expose verification_data without internal blob keys
    vd = doc.get("verification_data", {})
    doc["verification_data"] = {
        "type": vd.get("type"),
        "count": vd.get("count"),
        "avg_length": vd.get("avg_length"),
        "file_count": vd.get("file_count", 1),
        "available": bool(vd.get("blob_key") or vd.get("read_1_key")),
    }
    return doc


@router.get("/sample/{sample_id}", summary="List metaval results for a sample")
async def list_metaval_for_sample(
    sample_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    docs = (
        await db["metaval_results"]
        .find({"sample_id": _oid(sample_id)})
        .to_list(length=200)
    )
    return [_serialise(d) for d in docs]


@router.get("/{metaval_id}", summary="Get a single metaval result")
async def get_metaval(
    metaval_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["metaval_results"].find_one({"_id": _oid(metaval_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Metaval result not found")
    return _serialise(doc)


@router.post("/{metaval_id}/blast", summary="Submit verification data to NCBI BLAST")
async def blast_verification_data(
    metaval_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["metaval_results"].find_one({"_id": _oid(metaval_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Metaval result not found")

    vd = doc.get("verification_data", {})
    vd_type = vd.get("type")

    # For assembled data use the single blob key; for raw reads use read 1
    if vd_type in ("scaffolds", "contigs"):
        key = vd.get("blob_key")
    elif vd_type == "raw_reads":
        key = vd.get("read_1_key")
    else:
        key = None

    if not key:
        raise HTTPException(
            status_code=404, detail="Verification data not available for BLAST"
        )

    from app.database import get_blob_store

    fasta = await get_blob_store().get(key)
    if not fasta:
        raise HTTPException(
            status_code=404, detail="Verification data not found in storage"
        )

    def _submit_to_ncbi(fasta: str) -> str:
        import re

        response = http_requests.post(
            "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi",
            data={
                "CMD": "Put",
                "PROGRAM": "blastn",
                "DATABASE": "nt",
                "QUERY": fasta,
                "FORMAT_TYPE": "HTML",
                "MEGABLAST": "on",
                "HITLIST_SIZE": "10",
            },
            timeout=60,
        )
        response.raise_for_status()
        match = re.search(r"RID = ([A-Z0-9]+)", response.text)
        if not match:
            raise ValueError("Could not parse RID from NCBI response")
        return match.group(1)

    try:
        loop = asyncio.get_event_loop()
        rid = await loop.run_in_executor(None, _submit_to_ncbi, fasta)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"NCBI BLAST submission failed: {str(e)}"
        )

    return {
        "rid": rid,
        "results_url": f"https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?CMD=Get&FORMAT_TYPE=HTML&RID={rid}",
    }


@router.get(
    "/{metaval_id}/igv/{organism_name}",
    summary="Serve IGV HTML for a specific organism",
)
async def get_igv(
    metaval_id: str,
    organism_name: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["metaval_results"].find_one({"_id": _oid(metaval_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Metaval result not found")

    org = next(
        (o for o in doc.get("organisms", []) if o["organism_name"] == organism_name),
        None,
    )
    if not org:
        raise HTTPException(
            status_code=404, detail=f"Organism '{organism_name}' not found"
        )
    if org.get("igv_too_large"):
        raise HTTPException(status_code=413, detail="IGV file exceeds 10 MB limit")

    igv_key = org.get("igv_key")
    if not igv_key:
        raise HTTPException(status_code=404, detail="IGV HTML not available")

    from app.database import get_blob_store

    html = await get_blob_store().get(igv_key)
    if not html:
        raise HTTPException(status_code=404, detail="IGV HTML not found in storage")

    return HTMLResponse(content=html)
