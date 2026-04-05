# app/routers/cases.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional
from app.models.sample import CaseResponse

import json
from pathlib import Path

from app.database import get_db
from app.auth.utils import get_current_user, require_role
from app.config import settings


def _load_controls_taxa() -> dict:
    path = Path(settings.controls_taxa_path)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

router = APIRouter(prefix="/cases", tags=["cases"])


class ReviewPayload(BaseModel):
    notes: Optional[str] = None


def _serialise_case(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if "sample_ids" in doc:
        doc["sample_ids"] = [str(sid) for sid in doc["sample_ids"]]
    # case_id is already a plain string — no conversion needed
    return doc


def _serialise_sample(doc: dict) -> dict:
    doc["_id"]     = str(doc["_id"])
    doc["case_id"] = str(doc["case_id"])
    if doc.get("subject_id"):
        doc["subject_id"] = str(doc["subject_id"])
    return doc


HOST_TAXON_IDS = {9606, 1, 0, 131567}


def _non_host_total(entries: list, clf_qc: dict = None) -> float:
    host_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 9606), 0)
    if clf_qc and clf_qc.get("classified_reads") is not None:
        return clf_qc["classified_reads"] - host_reads
    root_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 1), 0)
    return root_reads - host_reads


def _top_taxa_for(entries: list, clf_qc: dict = None, n: int = 3) -> list:
    non_host_total = _non_host_total(entries, clf_qc)
    non_host_entries = [
        e for e in entries
        if e.get("taxon_id") not in HOST_TAXON_IDS
           and e.get("name") != "unclassified"
           and not (e.get("name") or "").startswith("unclassified ")
    ]
    non_host_entries.sort(key=lambda e: e.get("abundance", 0), reverse=True)
    return [
        {
            "name":         e["name"],
            "superkingdom": e.get("superkingdom"),
            "abundance":    e["abundance"],
            "pct":          round(e["abundance"] / non_host_total * 100, 3) if non_host_total else None,
        }
        for e in non_host_entries[:n]
    ]


def _spike_in_for(entries: list, spike_in_ids: set, clf_qc: dict = None) -> list:
    if not spike_in_ids:
        return []
    non_host_total = _non_host_total(entries, clf_qc)
    return [
        {
            "name":      e["name"],
            "taxon_id":  e["taxon_id"],
            "abundance": e["abundance"],
            "pct":       round(e["abundance"] / non_host_total * 100, 3) if non_host_total else None,
        }
        for e in entries
        if e.get("taxon_id") in spike_in_ids
    ]


def _host_pct_for(entries: list, clf_qc: dict = None) -> Optional[float]:
    host_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 9606), 0)
    classified_reads = clf_qc.get("classified_reads") if clf_qc else None
    if classified_reads is None:
        classified_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 1), 0)
    total_reads = host_reads + (clf_qc.get("unclassified_reads") or 0) if clf_qc else classified_reads
    if not total_reads:
        return None
    return round(host_reads / total_reads * 100, 1)


PAGE_SIZE = 50

@router.get("", summary="List all cases")
async def list_cases(
    page:   int = 1,
    search: str = "",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = {}
    if search.strip():
        query["case_id"] = {"$regex": search.strip(), "$options": "i"}

    total = await db["cases"].estimated_document_count() if not query else await db["cases"].count_documents(query)
    skip  = (page - 1) * PAGE_SIZE

    docs = await db["cases"].find(query).sort(
        [("review.reviewed", 1), ("order_date", -1), ("ingested_at", -1)]
    ).skip(skip).limit(PAGE_SIZE).to_list(length=PAGE_SIZE)

    result = []
    for doc in docs:
        doc.setdefault("sample_count",  0)
        doc.setdefault("control_count", 0)
        doc.setdefault("sample_names",  [])
        result.append(CaseResponse.model_validate(_serialise_case(doc)).model_dump(mode="json"))

    return {
        "total": total,
        "page":  page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        "items": result,
    }


@router.get("/{case_id}", summary="Get a single case")
async def get_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["cases"].find_one({"case_id": case_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    doc = _serialise_case(doc)
    return CaseResponse.model_validate(doc).model_dump(mode="json")


@router.get("/{case_id}/samples", summary="List samples for a case")
async def list_samples_for_case(
    case_id: str,
    type: str = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    case = await db["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    query: dict = {"case_id": case["_id"]}
    if type == "controls":
        query["sample_type"] = {"$in": ["positive_ctrl", "negative_ctrl"]}
    elif type == "sample":
        query["sample_type"] = "sample"

    docs = await db["samples"].find(query).to_list(length=200)

    controls_taxa = _load_controls_taxa()
    spike_in_ids = set(controls_taxa.get("spike_in", []))

    result = []
    for doc in docs:
        profiles = doc.get("profiles", [])
        top_taxa_by_clf = {}
        spike_in_by_clf = {}
        host_pct_by_clf = {}
        for p in profiles:
            clf = p.get("classifier", "unknown")
            entries = p.get("profile", [])
            clf_qc = doc.get("taxprofiler", {}).get("classifiers", {}).get(clf)
            top_taxa_by_clf[clf] = _top_taxa_for(entries, clf_qc)
            spike_in_by_clf[clf] = _spike_in_for(entries, spike_in_ids, clf_qc)
            host_pct_by_clf[clf] = _host_pct_for(entries, clf_qc)
        doc["top_taxa"] = top_taxa_by_clf
        doc["spike_in_taxa"] = spike_in_by_clf
        doc["host_pct"] = host_pct_by_clf
        doc.pop("profiles", None)
        result.append(_serialise_sample(doc))
    return result


@router.delete("/{case_id}", summary="Delete a case and all associated data")
async def delete_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    case = await db["cases"].find_one({"case_id": case_id}, {"_id": 1})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    oid = case["_id"]

    await db["samples"].delete_many({"case_id": oid})
    await db["krona_files"].delete_many({"case_id": oid})
    await db["metaval_results"].delete_many({"case_id": oid})
    await db["cases"].delete_one({"_id": oid})

    return {"deleted": True, "case_id": case_id}


@router.get("/{case_id}/krona", summary="Serve Krona HTML for a case")
async def get_krona(
    case_id: str,
    classifier: str = "kraken2",
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    case = await db["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    doc = await db["krona_files"].find_one({
        "case_id":    case["_id"],
        "classifier": classifier,
    })
    if not doc:
        raise HTTPException(status_code=404, detail=f"No Krona file for classifier '{classifier}'")

    return HTMLResponse(content=doc["html"])


@router.patch("/{case_id}/review", summary="Mark a case as reviewed by the current user")
async def review_case(
    case_id: str,
    payload: ReviewPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    result = await db["cases"].update_one(
        {"case_id": case_id},
        {
            "$set": {
                "review.reviewed":    True,
                "review.reviewed_by": current_user["username"],
                "review.reviewed_at": datetime.now(timezone.utc),
                "review.notes":       payload.notes,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return {"case_id": case_id, "reviewed": True, "reviewed_by": current_user["username"]}


@router.delete("/{case_id}/review", summary="Remove review from a case")
async def unreview_case(
    case_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    result = await db["cases"].update_one(
        {"case_id": case_id},
        {
            "$set": {
                "review.reviewed":    False,
                "review.reviewed_by": None,
                "review.reviewed_at": None,
                "review.notes":       None,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return {"case_id": case_id, "reviewed": False}


class NotePayload(BaseModel):
    text: str


@router.post("/{case_id}/notes", summary="Add a note to a case")
async def add_note(
    case_id: str,
    payload: NotePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Note text cannot be empty")
    note = {
        "text":       payload.text.strip(),
        "author":     current_user["username"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db["cases"].update_one(
        {"case_id": case_id},
        {"$push": {"notes": note}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return note


@router.delete("/{case_id}/notes/{note_index}", summary="Delete a note from a case")
async def delete_note(
    case_id: str,
    note_index: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    case = await db["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    notes = case.get("notes", [])
    if note_index < 0 or note_index >= len(notes):
        raise HTTPException(status_code=404, detail="Note not found")
    note = notes[note_index]
    if current_user["role"] != "admin" and note.get("author") != current_user["username"]:
        raise HTTPException(status_code=403, detail="You can only delete your own notes")
    # Remove by index using $unset + $pull trick
    notes.pop(note_index)
    await db["cases"].update_one(
        {"case_id": case_id},
        {"$set": {"notes": notes}},
    )
    return {"deleted": True}
