# app/taxon_lists/store.py
"""MongoDB access for ``taxon_lists`` and ``taxon_list_entries``.

The only module that touches either collection. Documents are validated into
models on the way out, so callers never handle raw dicts.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Collection, Optional, TypeVar

from motor.motor_asyncio import AsyncIOMotorClientSession, AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.db_utils import fetch_capped
from app.models.taxon_list import TaxonList, TaxonListEntry, TaxonListEntryOut
from app.taxon_lists.kinds import SYSTEM_LISTS, TaxonListKind
from app.taxon_lists.rules import ResolvedTaxon, RetiredTaxon

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


async def insert_list(db: AsyncIOMotorDatabase, taxon_list: TaxonList) -> None:
    """Insert *taxon_list*. Raises ``DuplicateKeyError`` on a list_id clash."""
    await db[LISTS].insert_one(taxon_list.model_dump())


async def update_list(
    db: AsyncIOMotorDatabase, list_id: str, changes: dict
) -> Optional[TaxonList]:
    doc = await db[LISTS].find_one_and_update(
        {"list_id": list_id},
        {"$set": changes},
        projection=_NO_ID,
        return_document=ReturnDocument.AFTER,
    )
    return TaxonList.model_validate(doc) if doc else None


async def delete_list(
    db: AsyncIOMotorDatabase,
    list_id: str,
    session: Optional[AsyncIOMotorClientSession] = None,
) -> int:
    """Delete a list and its entries; returns how many entries went with it.

    Entries go first, so a failure part-way through outside a transaction
    leaves an empty list behind rather than entries pointing at no list.
    """
    result = await db[ENTRIES].delete_many({"list_id": list_id}, session=session)
    await db[LISTS].delete_one({"list_id": list_id}, session=session)
    return result.deleted_count


async def existing_list_ids(
    db: AsyncIOMotorDatabase, list_ids: list[str], kind: TaxonListKind
) -> set[str]:
    """Which of *list_ids* exist with the given kind."""
    if not list_ids:
        return set()
    found = await db[LISTS].distinct(
        "list_id", {"list_id": {"$in": list_ids}, "kind": kind.value}
    )
    return set(found)


async def entry_counts(db: AsyncIOMotorDatabase, list_ids: list[str]) -> dict[str, int]:
    """Number of entries per list, for list overviews."""
    pipeline: list[dict] = [
        {"$match": {"list_id": {"$in": list_ids}}},
        {"$group": {"_id": "$list_id", "count": {"$sum": 1}}},
    ]
    rows = await db[ENTRIES].aggregate(pipeline).to_list(None)
    return {row["_id"]: row["count"] for row in rows}


async def list_lists(
    db: AsyncIOMotorDatabase, kind: Optional[TaxonListKind] = None
) -> list[TaxonList]:
    query: dict = {"kind": kind.value} if kind else {}
    docs = await fetch_capped(db[LISTS].find(query, _NO_ID).sort("name", 1), LISTS)
    return [TaxonList.model_validate(doc) for doc in docs]


# ---------------------------------------------------------------------------
# Entries — reads
# ---------------------------------------------------------------------------


# Entries are read in full, never capped: a list can hold tens of thousands of
# taxa (bulk add), and a silently truncated list would apply only part of an
# ignorelist or display filter. Callers that show entries page through
# ``page_entries`` instead.
_ENTRY_ORDER = [("added_at", -1), ("taxon_id", 1)]


async def list_entries(
    db: AsyncIOMotorDatabase,
    list_id: str,
    *,
    model: type[EntryT],
    superkingdom: Optional[str] = None,
) -> list[EntryT]:
    """Every entry of one list, newest first, validated as *model*.

    *model* is explicit so a consumer that relies on a kind-specific field
    (e.g. ``ContaminantEntry.min_reads``) states it, and a document missing
    that field fails validation instead of reaching the analytics.
    """
    query: dict = {"list_id": list_id}
    if superkingdom:
        query["superkingdom"] = superkingdom
    docs = await db[ENTRIES].find(query, _NO_ID).sort(_ENTRY_ORDER).to_list(None)
    return [model.model_validate(doc) for doc in docs]


async def page_entries(
    db: AsyncIOMotorDatabase,
    list_id: str,
    *,
    offset: int,
    limit: int,
    search: Optional[str] = None,
    superkingdom: Optional[str] = None,
) -> tuple[list[TaxonListEntry], int]:
    """One page of a list's entries, newest first, and the total matching.

    *search* matches a taxon id exactly when it is all digits, and otherwise
    a case-insensitive substring of the name.
    """
    query: dict = {"list_id": list_id}
    if superkingdom:
        query["superkingdom"] = superkingdom
    if search:
        term = search.strip()
        query["$or"] = [{"taxon_name": {"$regex": re.escape(term), "$options": "i"}}]
        if term.isdigit():
            query["$or"].append({"taxon_id": int(term)})
    total, docs = await asyncio.gather(
        db[ENTRIES].count_documents(query),
        db[ENTRIES]
        .find(query, _NO_ID)
        .sort(_ENTRY_ORDER)
        .skip(offset)
        .limit(limit)
        .to_list(None),
    )
    return [TaxonListEntry.model_validate(doc) for doc in docs], total


async def taxon_ids(db: AsyncIOMotorDatabase, list_id: str) -> frozenset[int]:
    """Every id the list matches: its taxa and the retired ids merged into them.

    Classifier databases are built on older taxonomy snapshots, so a sample can
    report an id NCBI has since merged. Lists store current ids; matching
    through the aliases catches the old form too.
    """
    docs = (
        await db[ENTRIES]
        .find({"list_id": list_id}, {"_id": 0, "taxon_id": 1})
        .to_list(None)
    )
    current = {int(doc["taxon_id"]) for doc in docs}
    aliases = await merged_aliases(db, current)
    return frozenset(current.union(*aliases.values()))


async def merged_aliases(
    db: AsyncIOMotorDatabase, taxon_ids: Collection[int]
) -> dict[int, list[int]]:
    """Retired ids NCBI merged into each of *taxon_ids*: current -> [old, ...].

    One indexed query (``merged_into_1_merged``) whatever the number of ids.
    One hop is enough: NCBI's merged.dmp maps every old id straight to a
    current one.
    """
    if not taxon_ids:
        return {}
    aliases: dict[int, list[int]] = {}
    async for doc in db["taxa_retired"].find(
        {"status": "merged", "merged_into": {"$in": list(taxon_ids)}},
        {"_id": 0, "taxon_id": 1, "merged_into": 1},
    ):
        aliases.setdefault(int(doc["merged_into"]), []).append(int(doc["taxon_id"]))
    for old_ids in aliases.values():
        old_ids.sort()
    return aliases


async def with_merged_ids(
    db: AsyncIOMotorDatabase, entries: list[TaxonListEntry]
) -> list[TaxonListEntryOut]:
    """*entries* as API responses, each with the retired ids it also matches."""
    aliases = await merged_aliases(db, {entry.taxon_id for entry in entries})
    return [
        TaxonListEntryOut(
            **entry.model_dump(), merged_ids=aliases.get(entry.taxon_id, [])
        )
        for entry in entries
    ]


async def existing_taxon_ids(
    db: AsyncIOMotorDatabase, list_id: str, taxon_ids: list[int]
) -> set[int]:
    """Which of *taxon_ids* are already on the list. One query for any batch."""
    found = await db[ENTRIES].distinct(
        "taxon_id", {"list_id": list_id, "taxon_id": {"$in": taxon_ids}}
    )
    return {int(taxon_id) for taxon_id in found}


async def kinds_by_taxon(
    db: AsyncIOMotorDatabase, taxon_ids: list[int]
) -> dict[int, set[TaxonListKind]]:
    """Kinds of every list each taxon is on. Two queries for any batch."""
    docs = (
        await db[ENTRIES]
        .find({"taxon_id": {"$in": taxon_ids}}, {"_id": 0, "taxon_id": 1, "list_id": 1})
        .to_list(None)
    )
    if not docs:
        return {}
    list_kinds = {
        doc["list_id"]: TaxonListKind(doc["kind"])
        async for doc in db[LISTS].find(
            {"list_id": {"$in": list({d["list_id"] for d in docs})}},
            {"_id": 0, "list_id": 1, "kind": 1},
        )
    }
    kinds: dict[int, set[TaxonListKind]] = {}
    for doc in docs:
        kind = list_kinds.get(doc["list_id"])
        if kind is not None:
            kinds.setdefault(int(doc["taxon_id"]), set()).add(kind)
    return kinds


# ---------------------------------------------------------------------------
# Entries — writes
# ---------------------------------------------------------------------------


async def insert_entries(
    db: AsyncIOMotorDatabase,
    entries: list[TaxonListEntry],
    session: Optional[AsyncIOMotorClientSession] = None,
) -> None:
    """Insert *entries* in one round trip.

    Raises ``BulkWriteError`` (a ``DuplicateKeyError`` for a single entry is
    wrapped the same way) if any is already on its list. Run it in a
    transaction for all-or-nothing.
    """
    await db[ENTRIES].insert_many(
        [entry.model_dump() for entry in entries], session=session
    )


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


async def resolve_taxa(
    db: AsyncIOMotorDatabase, taxon_ids: list[int]
) -> dict[int, ResolvedTaxon | RetiredTaxon]:
    """Look *taxon_ids* up the way the clade view does; absent ids are unknown.

    ``taxa_retired`` wins over ``taxa`` because upserts never delete: a
    retired ID can linger in ``taxa`` with stale data. Ingest-time placeholder
    documents count as found — they carry the name and superkingdom the
    classifier reported, which is all a list entry needs. Two queries for any
    batch.
    """
    found: dict[int, ResolvedTaxon | RetiredTaxon] = {}
    async for doc in db["taxa"].find(
        {"taxon_id": {"$in": taxon_ids}},
        {"_id": 0, "taxon_id": 1, "name": 1, "superkingdom": 1},
    ):
        if doc.get("name"):
            taxon_id = int(doc["taxon_id"])
            found[taxon_id] = ResolvedTaxon(
                taxon_id=taxon_id,
                name=doc["name"],
                superkingdom=doc.get("superkingdom"),
            )
    async for doc in db["taxa_retired"].find(
        {"taxon_id": {"$in": taxon_ids}},
        {"_id": 0, "taxon_id": 1, "status": 1, "merged_into": 1},
    ):
        found[int(doc["taxon_id"])] = RetiredTaxon(
            status=doc["status"], merged_into=doc.get("merged_into")
        )
    return found
