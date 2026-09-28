# app/taxon_lists/service.py
"""Taxon-list writes, end to end: validate, persist, invalidate caches, audit."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.audit import log_audit_event
from app.cache import bump_cache_version
from app.models.taxon_list import (
    TaxonList,
    TaxonListEntry,
    TaxonListEntryCreate,
    TaxonListEntryUpdate,
)
from app.taxon_lists import rules, store
from app.taxon_lists.kinds import KIND_SPECS

_RESOURCE_TYPE = "taxon_list_entry"


async def require_list(db: AsyncIOMotorDatabase, list_id: str) -> TaxonList:
    taxon_list = await store.get_list(db, list_id)
    if taxon_list is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Taxon list {list_id!r} not found"
        )
    return taxon_list


async def add_entry(
    db: AsyncIOMotorDatabase,
    list_id: str,
    payload: TaxonListEntryCreate,
    actor: str,
) -> TaxonListEntry:
    taxon_list = await require_list(db, list_id)
    extras = _validated_extras(taxon_list, payload.kind_specific_fields())
    taxon = await _resolve_taxon(db, payload.taxon_id)

    if await store.get_entry(db, list_id, payload.taxon_id):
        raise _already_on(payload.taxon_id, taxon_list)
    conflicts = rules.conflicting_kinds(
        taxon_list.kind, await store.kinds_containing(db, payload.taxon_id)
    )
    if conflicts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Taxon {payload.taxon_id} is on a list of kind "
                f"{', '.join(sorted(conflicts))}, which excludes "
                f"{taxon_list.name!r}. Remove it from there first."
            ),
        )

    entry = TaxonListEntry.model_validate(
        {
            "list_id": list_id,
            "taxon_id": taxon.taxon_id,
            "taxon_name": taxon.name,
            "superkingdom": taxon.superkingdom,
            "reason": payload.reason,
            **rules.with_defaults(taxon_list.kind, extras),
            "added_by": actor,
            "added_at": datetime.now(timezone.utc),
        }
    )
    try:
        await store.insert_entry(db, entry)
    except DuplicateKeyError:
        # Lost a race with a concurrent add of the same taxon.
        raise _already_on(payload.taxon_id, taxon_list) from None

    await _after_change(
        db, taxon_list, "add", payload.taxon_id, actor, entry.model_dump(mode="json")
    )
    return entry


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


async def _resolve_taxon(
    db: AsyncIOMotorDatabase, taxon_id: int
) -> store.ResolvedTaxon:
    resolved = await store.resolve_taxon(db, taxon_id)
    if isinstance(resolved, store.RetiredTaxon):
        if resolved.merged_into is not None:
            detail = (
                f"Taxon {taxon_id} was merged into {resolved.merged_into} "
                f"in the NCBI taxonomy; add {resolved.merged_into} instead"
            )
        else:
            detail = f"Taxon {taxon_id} was deleted from the NCBI taxonomy"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    if resolved is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Taxon {taxon_id} is not in the taxa collection. "
                "Check the ID, or run load_taxonomy.py to populate reference data."
            ),
        )
    return resolved


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
