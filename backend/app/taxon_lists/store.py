# app/taxon_lists/store.py
"""MongoDB access for ``taxon_lists`` and ``taxon_list_entries``.

The only module that touches either collection. Documents are validated into
models on the way out, so callers never handle raw dicts.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional, TypeVar

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db_utils import fetch_capped
from app.models.taxon_list import TaxonList, TaxonListEntry
from app.taxon_lists.kinds import SYSTEM_LISTS, TaxonListKind

LISTS = "taxon_lists"
ENTRIES = "taxon_list_entries"

EntryT = TypeVar("EntryT", bound=TaxonListEntry)

_NO_ID = {"_id": 0}


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


async def seed_system_lists(db: AsyncIOMotorDatabase) -> None:
    """Create the system lists if missing. Idempotent; runs at every startup.

    Name and description follow the code, so a rename in ``SYSTEM_LISTS``
    reaches existing databases; provenance is written only on first insert.
    """
    now = datetime.now(timezone.utc)
    for spec in SYSTEM_LISTS:
        await db[LISTS].update_one(
            {"list_id": spec.list_id},
            {
                "$set": {
                    "kind": spec.kind.value,
                    "name": spec.name,
                    "description": spec.description,
                    "system": True,
                },
                "$setOnInsert": {
                    "created_by": "system",
                    "created_at": now,
                    "updated_at": now,
                },
            },
            upsert=True,
        )


async def get_list(db: AsyncIOMotorDatabase, list_id: str) -> Optional[TaxonList]:
    doc = await db[LISTS].find_one({"list_id": list_id}, _NO_ID)
    return TaxonList.model_validate(doc) if doc else None


async def list_lists(
    db: AsyncIOMotorDatabase, kind: Optional[TaxonListKind] = None
) -> list[TaxonList]:
    query: dict = {"kind": kind.value} if kind else {}
    docs = await fetch_capped(db[LISTS].find(query, _NO_ID).sort("name", 1), LISTS)
    return [TaxonList.model_validate(doc) for doc in docs]


# ---------------------------------------------------------------------------
# Entries — reads
# ---------------------------------------------------------------------------


async def list_entries(
    db: AsyncIOMotorDatabase,
    list_id: str,
    *,
    model: type[EntryT],
    superkingdom: Optional[str] = None,
) -> list[EntryT]:
    """Entries of one list, newest first, validated as *model*.

    *model* is explicit so a consumer that relies on a kind-specific field
    (e.g. ``ContaminantEntry.min_reads``) states it, and a document missing
    that field fails validation instead of reaching the analytics.
    """
    query: dict = {"list_id": list_id}
    if superkingdom:
        query["superkingdom"] = superkingdom
    docs = await fetch_capped(
        db[ENTRIES].find(query, _NO_ID).sort("added_at", -1), f"{ENTRIES}:{list_id}"
    )
    return [model.model_validate(doc) for doc in docs]


async def taxon_ids(db: AsyncIOMotorDatabase, list_id: str) -> frozenset[int]:
    """The taxon IDs on one list — what the analytics exclude or match on."""
    docs = await fetch_capped(
        db[ENTRIES].find({"list_id": list_id}, {"_id": 0, "taxon_id": 1}),
        f"{ENTRIES}:{list_id}",
    )
    return frozenset(int(doc["taxon_id"]) for doc in docs)


async def get_entry(
    db: AsyncIOMotorDatabase, list_id: str, taxon_id: int
) -> Optional[TaxonListEntry]:
    doc = await db[ENTRIES].find_one({"list_id": list_id, "taxon_id": taxon_id}, _NO_ID)
    return TaxonListEntry.model_validate(doc) if doc else None


async def kinds_containing(
    db: AsyncIOMotorDatabase, taxon_id: int
) -> set[TaxonListKind]:
    """Kinds of every list the taxon is currently on."""
    list_ids = await db[ENTRIES].distinct("list_id", {"taxon_id": taxon_id})
    if not list_ids:
        return set()
    kinds = await db[LISTS].distinct("kind", {"list_id": {"$in": list_ids}})
    return {TaxonListKind(kind) for kind in kinds}


# ---------------------------------------------------------------------------
# Entries — writes
# ---------------------------------------------------------------------------


async def insert_entry(db: AsyncIOMotorDatabase, entry: TaxonListEntry) -> None:
    """Insert *entry*. Raises ``DuplicateKeyError`` if it is already on the list."""
    await db[ENTRIES].insert_one(entry.model_dump())


async def update_entry(
    db: AsyncIOMotorDatabase, list_id: str, taxon_id: int, changes: dict
) -> Optional[TaxonListEntry]:
    """Apply *changes*; the updated entry, or None when there is no such entry."""
    doc = await db[ENTRIES].find_one_and_update(
        {"list_id": list_id, "taxon_id": taxon_id},
        {"$set": changes},
        projection=_NO_ID,
        return_document=ReturnDocument.AFTER,
    )
    return TaxonListEntry.model_validate(doc) if doc else None


async def delete_entry(db: AsyncIOMotorDatabase, list_id: str, taxon_id: int) -> bool:
    result = await db[ENTRIES].delete_one({"list_id": list_id, "taxon_id": taxon_id})
    return result.deleted_count > 0


# ---------------------------------------------------------------------------
# Taxonomy lookup
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedTaxon:
    taxon_id: int
    name: str
    superkingdom: Optional[str]


@dataclass(frozen=True)
class RetiredTaxon:
    status: Literal["merged", "deleted"]
    merged_into: Optional[int]


async def resolve_taxon(
    db: AsyncIOMotorDatabase, taxon_id: int
) -> ResolvedTaxon | RetiredTaxon | None:
    """Look *taxon_id* up the way the clade view does.

    ``taxa_retired`` is consulted first because upserts never delete: a
    retired ID can linger in ``taxa`` with stale data. Ingest-time placeholder
    documents count as found — they carry the name and superkingdom the
    classifier reported, which is all a list entry needs.
    """
    retired = await db["taxa_retired"].find_one(
        {"taxon_id": taxon_id}, {"_id": 0, "status": 1, "merged_into": 1}
    )
    if retired:
        return RetiredTaxon(
            status=retired["status"], merged_into=retired.get("merged_into")
        )
    doc = await db["taxa"].find_one(
        {"taxon_id": taxon_id}, {"_id": 0, "name": 1, "superkingdom": 1}
    )
    if not doc or not doc.get("name"):
        return None
    return ResolvedTaxon(
        taxon_id=taxon_id, name=doc["name"], superkingdom=doc.get("superkingdom")
    )
