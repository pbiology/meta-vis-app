# app/routers/taxon_lists.py
"""Curated taxon lists — one API for every kind (see app/taxon_lists/)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user, require_role
from app.database import get_db
from app.models.taxon_list import (
    TaxonList,
    TaxonListEntry,
    TaxonListEntryCreate,
    TaxonListEntryUpdate,
)
from app.taxon_lists import service, store
from app.taxon_lists.kinds import TaxonListKind

router = APIRouter(prefix="/taxon-lists", tags=["taxon-lists"])


@router.get("", summary="List taxon lists")
async def get_taxon_lists(
    kind: Optional[TaxonListKind] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[TaxonList]:
    return await store.list_lists(db, kind)


@router.get("/{list_id}", summary="Get one taxon list")
async def get_taxon_list(
    list_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> TaxonList:
    return await service.require_list(db, list_id)


@router.get("/{list_id}/entries", summary="List the taxa on a list")
async def get_entries(
    list_id: str,
    superkingdom: Optional[str] = Query(
        None, description="Filter by superkingdom (e.g. 'Viruses')"
    ),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[TaxonListEntry]:
    await service.require_list(db, list_id)
    return await store.list_entries(
        db, list_id, model=TaxonListEntry, superkingdom=superkingdom
    )


@router.post(
    "/{list_id}/entries",
    summary="Add a taxon to a list",
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    list_id: str,
    payload: TaxonListEntryCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> TaxonListEntry:
    return await service.add_entry(db, list_id, payload, current_user["username"])


@router.patch("/{list_id}/entries/{taxon_id}", summary="Update a list entry")
async def update_entry(
    list_id: str,
    taxon_id: int,
    payload: TaxonListEntryUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> TaxonListEntry:
    return await service.update_entry(
        db, list_id, taxon_id, payload, current_user["username"]
    )


@router.delete(
    "/{list_id}/entries/{taxon_id}",
    summary="Remove a taxon from a list",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_entry(
    list_id: str,
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
) -> Response:
    await service.remove_entry(db, list_id, taxon_id, current_user["username"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
