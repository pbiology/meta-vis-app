# app/taxon_lists/service.py
"""Taxon-list writes, end to end: validate, persist, invalidate caches, audit."""

import asyncio
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError, DuplicateKeyError

from app.audit import log_audit_event
from app.cache import bump_cache_version
from app.database import get_client, maybe_transaction
from app.models.taxon_list import (
    BULK_SAMPLE_SIZE,
    BulkAddReport,
    RejectedTaxon,
    ReplacedTaxon,
    TaxonList,
    TaxonListBulkAdd,
    TaxonListCreate,
    TaxonListEntry,
    TaxonListEntryCreate,
    TaxonListEntryUpdate,
    TaxonListUpdate,
    TaxonToAdd,
)
from app.taxon_lists import rules, store
from app.taxon_lists.kinds import KIND_SPECS, TaxonListKind

_RESOURCE_TYPE = "taxon_list_entry"
_LIST_RESOURCE_TYPE = "taxon_list"

# Preference field holding a user's active display filters. Kept here, next to
# the delete that must clean it, rather than importing the users router.
_ACTIVE_FILTERS_FIELD = "preferences.active_display_filters"


async def require_list(db: AsyncIOMotorDatabase, list_id: str) -> TaxonList:
    taxon_list = await store.get_list(db, list_id)
    if taxon_list is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Taxon list {list_id!r} not found"
        )
    return taxon_list


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


async def create_list(
    db: AsyncIOMotorDatabase, payload: TaxonListCreate, actor: str
) -> TaxonList:
    if not KIND_SPECS[payload.kind].user_creatable:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Lists of kind {payload.kind.value!r} cannot be created",
        )
    now = datetime.now(timezone.utc)
    taxon_list = TaxonList(
        # Generated rather than derived from the name: stable across renames,
        # and a clash is practically impossible (retried once below regardless).
        list_id=_new_list_id(payload.kind),
        kind=payload.kind,
        name=payload.name,
        description=payload.description,
        system=False,
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    try:
        await store.insert_list(db, taxon_list)
    except DuplicateKeyError:
        taxon_list = taxon_list.model_copy(
            update={"list_id": _new_list_id(payload.kind)}
        )
        await store.insert_list(db, taxon_list)
    await _audit_list(db, "create", taxon_list, actor, {"name": taxon_list.name})
    return taxon_list


async def update_list(
    db: AsyncIOMotorDatabase, list_id: str, payload: TaxonListUpdate, actor: str
) -> TaxonList:
    existing = _require_user_list(await require_list(db, list_id), "renamed")
    changes = payload.model_dump(exclude_unset=True)
    updated = await store.update_list(
        db, list_id, {**changes, "updated_at": datetime.now(timezone.utc)}
    )
    if updated is None:
        # Deleted between the lookup and the update.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Taxon list {list_id!r} not found"
        )
    await _audit_list(db, "update", existing, actor, changes)
    return updated


async def delete_list(db: AsyncIOMotorDatabase, list_id: str, actor: str) -> None:
    taxon_list = _require_user_list(await require_list(db, list_id), "deleted")
    async with maybe_transaction(get_client()) as session:
        removed_entries = await store.delete_list(db, list_id, session=session)
        # No user may keep a deleted list active: an unknown id would fail
        # their next preferences save.
        await db["users"].update_many(
            {_ACTIVE_FILTERS_FIELD: list_id},
            {"$pull": {_ACTIVE_FILTERS_FIELD: list_id}},
            session=session,
        )
    await _audit_list(
        db, "delete", taxon_list, actor, {"removed_entries": removed_entries}
    )


def _new_list_id(kind: TaxonListKind) -> str:
    prefix = "df" if kind is TaxonListKind.DISPLAY_FILTER else kind.value
    return f"{prefix}-{secrets.token_hex(4)}"


def _require_user_list(taxon_list: TaxonList, verb: str) -> TaxonList:
    if taxon_list.system:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"System list {taxon_list.list_id!r} cannot be {verb}",
        )
    return taxon_list


async def _audit_list(
    db: AsyncIOMotorDatabase,
    verb: str,
    taxon_list: TaxonList,
    actor: str,
    detail: dict,
) -> None:
    await log_audit_event(
        db,
        action=f"taxon_list_{verb}",
        actor=actor,
        resource_type=_LIST_RESOURCE_TYPE,
        resource_id=taxon_list.list_id,
        outcome="success",
        detail={"kind": taxon_list.kind.value, **detail},
    )


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


async def add_entry(
    db: AsyncIOMotorDatabase,
    list_id: str,
    payload: TaxonListEntryCreate,
    actor: str,
) -> TaxonListEntry:
    taxon_list = await require_list(db, list_id)
    extras = _validated_extras(taxon_list, payload.kind_specific_fields())
    result = await _classify(db, taxon_list, [payload.taxon_id])
    if result.already_on_list:
        current = (
            result.replacements[0].merged_into
            if result.replacements
            else payload.taxon_id
        )
        raise _already_on(current, taxon_list)
    if result.rejected:
        rejection = result.rejected[0]
        code = (
            status.HTTP_409_CONFLICT
            if rejection.reason == "excluded_by_list"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(code, detail=rejection.detail)

    entry = _new_entry(taxon_list, result.to_add[0], payload.reason, extras, actor)
    try:
        await store.insert_entries(db, [entry])
    except (DuplicateKeyError, BulkWriteError):
        # Lost a race with a concurrent add of the same taxon.
        raise _already_on(payload.taxon_id, taxon_list) from None

    detail = entry.model_dump(mode="json")
    if result.replacements:
        detail["replaced_merged_id"] = payload.taxon_id
    await _after_change(db, taxon_list, "add", entry.taxon_id, actor, detail)
    return entry


async def bulk_add_entries(
    db: AsyncIOMotorDatabase,
    list_id: str,
    payload: TaxonListBulkAdd,
    actor: str,
) -> BulkAddReport:
    """Add many taxa, all or nothing, after the caller has seen a dry run.

    A real run re-classifies: if anything would now be rejected — the list or
    the taxonomy changed since the preview — nothing is written and the fresh
    report comes back in the 422, so no taxon is dropped without the user
    seeing it. Ids already on the list are skipped, not errors.
    """
    taxon_list = await require_list(db, list_id)
    extras = _validated_extras(taxon_list, payload.kind_specific_fields())
    result = await _classify(db, taxon_list, payload.taxon_ids)
    report = _report(result, added=0)
    if payload.dry_run or not result.to_add:
        return report
    if result.rejected:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": f"{len(result.rejected)} taxa cannot be added; nothing was added",
                "report": report.model_dump(),
            },
        )

    entries = [
        _new_entry(taxon_list, taxon, payload.reason, extras, actor)
        for taxon in result.to_add
    ]
    try:
        async with maybe_transaction(get_client()) as session:
            await store.insert_entries(db, entries, session=session)
    except BulkWriteError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Some of these taxa were added to the list meanwhile; check again",
        ) from None

    if KIND_SPECS[taxon_list.kind].affects_analytics:
        await bump_cache_version(db)
    await log_audit_event(
        db,
        action="taxon_list_entry_bulk_add",
        actor=actor,
        resource_type=_LIST_RESOURCE_TYPE,
        resource_id=taxon_list.list_id,
        outcome="success",
        detail={
            "kind": taxon_list.kind.value,
            "added": len(entries),
            "taxon_ids": [entry.taxon_id for entry in entries],
            "skipped_already_on_list": result.already_on_list,
            # [requested, current] pairs: BSON keys must be strings, not ids.
            "replaced": [[r.taxon_id, r.merged_into] for r in result.replacements],
            "reason": payload.reason,
            **extras,
        },
    )
    return _report(result, added=len(entries))


async def update_entry(
    db: AsyncIOMotorDatabase,
    list_id: str,
    taxon_id: int,
    payload: TaxonListEntryUpdate,
    actor: str,
) -> TaxonListEntry:
    taxon_list = await require_list(db, list_id)
    extras = _validated_extras(taxon_list, payload.kind_specific_fields())

    changes: dict = dict(extras)
    if "reason" in payload.model_fields_set:
        changes["reason"] = payload.reason
    changed_fields = sorted(changes)
    changes["updated_by"] = actor
    changes["updated_at"] = datetime.now(timezone.utc)

    entry = await store.update_entry(db, list_id, taxon_id, changes)
    if entry is None:
        raise _not_on(taxon_id, taxon_list)
    await _after_change(
        db,
        taxon_list,
        "update",
        taxon_id,
        actor,
        {"changed_fields": changed_fields, **payload.model_dump(exclude_unset=True)},
    )
    return entry


async def remove_entry(
    db: AsyncIOMotorDatabase, list_id: str, taxon_id: int, actor: str
) -> None:
    taxon_list = await require_list(db, list_id)
    if not await store.delete_entry(db, list_id, taxon_id):
        raise _not_on(taxon_id, taxon_list)
    await _after_change(db, taxon_list, "remove", taxon_id, actor, {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validated_extras(taxon_list: TaxonList, provided: dict[str, object]) -> dict:
    wrong_kind = rules.disallowed_fields(taxon_list.kind, provided)
    if wrong_kind:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{', '.join(wrong_kind)} not accepted by list {taxon_list.list_id!r} "
                f"(kind {taxon_list.kind.value})"
            ),
        )
    nulled = rules.nulled_fields(provided)
    if nulled:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{', '.join(nulled)} cannot be null",
        )
    return dict(provided)


async def _classify(
    db: AsyncIOMotorDatabase, taxon_list: TaxonList, taxon_ids: list[int]
) -> rules.Classification:
    ids = list(dict.fromkeys(taxon_ids))
    resolved = await store.resolve_taxa(db, ids)
    # Merged ids are replaced by their current id, which must be resolved too
    # and checked against the list and its exclusions like a requested id.
    replacements = {
        found.merged_into
        for found in resolved.values()
        if isinstance(found, rules.RetiredTaxon) and found.merged_into is not None
    } - set(ids)
    if replacements:
        resolved = {**resolved, **await store.resolve_taxa(db, list(replacements))}
    candidates = ids + sorted(replacements)
    # Independent lookups: a fixed number of queries whatever the batch size.
    already_on, kinds = await asyncio.gather(
        store.existing_taxon_ids(db, taxon_list.list_id, candidates),
        store.kinds_by_taxon(db, candidates),
    )
    return rules.classify_taxa(
        taxon_list.kind, taxon_list.name, ids, resolved, already_on, kinds
    )


def _new_entry(
    taxon_list: TaxonList,
    taxon: rules.ResolvedTaxon,
    reason: Optional[str],
    extras: dict,
    actor: str,
) -> TaxonListEntry:
    return TaxonListEntry.model_validate(
        {
            "list_id": taxon_list.list_id,
            "taxon_id": taxon.taxon_id,
            "taxon_name": taxon.name,
            "superkingdom": taxon.superkingdom,
            "reason": reason,
            **rules.with_defaults(taxon_list.kind, extras),
            "added_by": actor,
            "added_at": datetime.now(timezone.utc),
        }
    )


def _report(result: rules.Classification, added: int) -> BulkAddReport:
    return BulkAddReport(
        to_add_count=len(result.to_add),
        to_add_sample=[
            TaxonToAdd(
                taxon_id=t.taxon_id, taxon_name=t.name, superkingdom=t.superkingdom
            )
            for t in result.to_add[:BULK_SAMPLE_SIZE]
        ],
        already_on_list=result.already_on_list,
        replaced=[
            ReplacedTaxon(taxon_id=r.taxon_id, merged_into=r.merged_into)
            for r in result.replacements
        ],
        rejected=[
            RejectedTaxon(
                taxon_id=r.taxon_id, reason=r.reason, merged_into=r.merged_into
            )
            for r in result.rejected
        ],
        added=added,
    )


async def _after_change(
    db: AsyncIOMotorDatabase,
    taxon_list: TaxonList,
    verb: str,
    taxon_id: int,
    actor: str,
    detail: dict,
) -> None:
    if KIND_SPECS[taxon_list.kind].affects_analytics:
        await bump_cache_version(db)
    await log_audit_event(
        db,
        action=f"taxon_list_entry_{verb}",
        actor=actor,
        resource_type=_RESOURCE_TYPE,
        resource_id=f"{taxon_list.list_id}:{taxon_id}",
        outcome="success",
        detail={
            "list_id": taxon_list.list_id,
            "kind": taxon_list.kind.value,
            "taxon_id": taxon_id,
            **detail,
        },
    )


def _already_on(taxon_id: int, taxon_list: TaxonList) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail=f"Taxon {taxon_id} is already on {taxon_list.name!r}",
    )


def _not_on(taxon_id: int, taxon_list: TaxonList) -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail=f"Taxon {taxon_id} is not on {taxon_list.name!r}",
    )
