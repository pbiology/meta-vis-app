# app/routers/taxon_lists.py
"""Curated taxon lists — one API for every kind (see app/taxon_lists/)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user, require_role
from app.database import get_db
from app.models.taxon_list import (
    BulkAddReport,
    TaxonList,
    TaxonListBulkAdd,
    TaxonListCreate,
    TaxonListEntry,
    TaxonListEntryCreate,
    TaxonListEntryPage,
    TaxonListEntryUpdate,
    TaxonListSummary,
    TaxonListTaxonIds,
    TaxonListUpdate,
)
from app.taxon_lists import service, store
from app.taxon_lists.kinds import TaxonListKind

router = APIRouter(prefix="/taxon-lists", tags=["taxon-lists"])

# Largest page of entries one request may ask for. The full-list views ask for
# this and treat a larger ``total`` as an error rather than show part of it.
MAX_ENTRIES_PAGE = 10_000


@router.get("", summary="List taxon lists")
async def get_taxon_lists(
    kind: Optional[TaxonListKind] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[TaxonListSummary]:
    lists = await store.list_lists(db, kind)
    counts = await store.entry_counts(db, [taxon_list.list_id for taxon_list in lists])
    return [
        TaxonListSummary(
            **taxon_list.model_dump(), entry_count=counts.get(taxon_list.list_id, 0)
        )
        for taxon_list in lists
    ]


@router.post(
    "",
    summary="Create a taxon list (user-creatable kinds only)",
    status_code=status.HTTP_201_CREATED,
)
async def create_taxon_list(
    payload: TaxonListCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> TaxonList:
    return await service.create_list(db, payload, current_user["username"])


@router.patch("/{list_id}", summary="Rename or re-describe a taxon list")
async def update_taxon_list(
    list_id: str,
    payload: TaxonListUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> TaxonList:
    return await service.update_list(db, list_id, payload, current_user["username"])


@router.delete(
    "/{list_id}",
    summary="Delete a taxon list and its entries",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_taxon_list(
    list_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
) -> Response:
    await service.delete_list(db, list_id, current_user["username"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{list_id}", summary="Get one taxon list")
async def get_taxon_list(
    list_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> TaxonList:
    return await service.require_list(db, list_id)


@router.get("/{list_id}/entries", summary="One page of the taxa on a list")
async def get_entries(
    list_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_ENTRIES_PAGE),
    q: Optional[str] = Query(
        None, max_length=100, description="Taxon id, or part of the name"
    ),
    superkingdom: Optional[str] = Query(
        None, description="Filter by superkingdom (e.g. 'Viruses')"
    ),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> TaxonListEntryPage:
    await service.require_list(db, list_id)
    items, total = await store.page_entries(
        db, list_id, offset=offset, limit=limit, search=q, superkingdom=superkingdom
    )
    return TaxonListEntryPage(
        items=await store.with_merged_ids(db, items),
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{list_id}/taxon-ids",
    summary="Every id a list matches: its taxa and the retired ids merged into them",
)
async def get_taxon_ids(
    list_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> TaxonListTaxonIds:
    await service.require_list(db, list_id)
    ids = sorted(await store.taxon_ids(db, list_id))
    return TaxonListTaxonIds(list_id=list_id, count=len(ids), taxon_ids=ids)


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


@router.post(
    "/{list_id}/entries/bulk",
    summary="Add many taxa at once (use dry_run to preview)",
)
async def bulk_add_entries(
    list_id: str,
    payload: TaxonListBulkAdd,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
) -> BulkAddReport:
    return await service.bulk_add_entries(
        db, list_id, payload, current_user["username"]
    )


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
