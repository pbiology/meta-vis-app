# app/clade/loader.py
"""Fetch everything the clade view needs and assemble the response.

Cost is bounded by one analysis — the viewed sample plus its negative controls
— never by the number of samples in the database. Every taxonomy lookup is a
``taxon_id $in`` over the IDs in those profiles, on the unique ``taxon_id``
index; nothing queries ``taxa`` by ancestor alone.
"""

from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.clade.tree import (
    LineageRecord,
    RetiredRecord,
    build_tree,
    column_signal,
    connector_ids,
    pick_anchor_id,
    resolve_retired,
    unplaced_taxa,
)
from app.models.clade import CladeColumn, CladeResponse, CladeTaxon, CladeUnit
from app.sample_controls import matching_negative_controls

_SAMPLE_PROJECTION: dict[str, Any] = {
    "sample_id": 1,
    "sample_type": 1,
    "analysis_id": 1,
    "nucleic_acid": 1,
    "trana": 1,
    "profiles": 1,
}
_CONTROL_PROJECTION: dict[str, Any] = {
    "sample_id": 1,
    "sample_type": 1,
    "profiles": 1,
}
_LINEAGE_PROJECTION: dict[str, Any] = {
    "_id": 0,
    "taxon_id": 1,
    "name": 1,
    "rank": 1,
    "ancestor_ids": 1,
    "taxdump_version": 1,
}

TAXONOMY_REFRESH_DETAIL = (
    "The taxonomy reference predates lineage support. "
    "Re-run load_taxonomy.py to enable this view."
)


async def load_clade(
    db: AsyncIOMotorDatabase, sample_oid: ObjectId, classifier: str, taxon_id: int
) -> CladeResponse:
    """Build the clade view for one clicked taxon in one sample's profile.

    Raises 404 for an unknown sample, a classifier the sample has no profile
    for, or a clicked taxon that cannot be placed; 409 when the taxonomy
    reference needs reloading.
    """
    sample = await db["samples"].find_one({"_id": sample_oid}, _SAMPLE_PROJECTION)
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_oid}' not found")
    sample_entries = _classifier_entries(sample, classifier)
    if sample_entries is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sample has no profile for classifier '{classifier}'",
        )
    controls = await matching_negative_controls(db, sample, _CONTROL_PROJECTION)

    # --- Columns and their signal ------------------------------------------
    unit: CladeUnit = "fraction" if sample.get("trana") else "reads"
    columns: list[CladeColumn] = []
    signal: dict[str, dict[int, float]] = {}
    totals: dict[str, Optional[float]] = {}
    names: dict[int, str] = {}
    for doc, entries in [(sample, sample_entries)] + [
        (control, _classifier_entries(control, classifier)) for control in controls
    ]:
        sample_id = str(doc["sample_id"])
        total: Optional[float] = None
        if entries is not None:
            signal[sample_id], profile_total = column_signal(entries)
            total = profile_total if unit == "reads" else None
            totals[sample_id] = total
            names.update(
                (int(e["taxon_id"]), str(e["name"])) for e in entries if e.get("name")
            )
        columns.append(
            CladeColumn(
                sample_id=sample_id,
                sample_type=doc["sample_type"],
                has_profile=entries is not None,
                classifier_total=total,
            )
        )

    profile_ids = {tid for per_taxon in signal.values() for tid in per_taxon}
    retired = await _retired_records(db, profile_ids | {taxon_id})
    resolved = resolve_retired(signal, retired)

    # --- Anchor ------------------------------------------------------------
    clicked = await _lineage_record(db, _current_id(taxon_id, retired))
    genus = await db["taxa"].find_one(
        {"taxon_id": {"$in": clicked.ancestor_ids}, "rank": "genus"},
        {"_id": 0, "taxon_id": 1},
    )
    anchor_id = pick_anchor_id(clicked, genus["taxon_id"] if genus else None)
    anchor = (
        clicked
        if anchor_id == clicked.taxon_id
        else await _lineage_record(db, anchor_id)
    )

    # --- Tree --------------------------------------------------------------
    current_ids = [tid for per_taxon in resolved.values.values() for tid in per_taxon]
    members = await _lineage_records(
        db,
        {
            "taxon_id": {"$in": list(set(current_ids))},
            "$or": [{"taxon_id": anchor_id}, {"ancestor_ids": anchor_id}],
        },
    )
    records = {anchor_id: anchor, **{m.taxon_id: m for m in members}}
    needed = connector_ids(anchor_id, records.values())
    if needed:
        connectors = await _lineage_records(db, {"taxon_id": {"$in": list(needed)}})
        records.update((c.taxon_id, c) for c in connectors)
    try:
        root = build_tree(anchor_id, records, resolved, totals, columns[0].sample_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Taxonomy reference is inconsistent ({exc}). "
            "Re-run load_taxonomy.py.",
        ) from exc

    placed = await db["taxa"].distinct(
        "taxon_id",
        {
            "taxon_id": {"$in": list(set(current_ids))},
            "ancestor_ids": {"$type": "array"},
        },
    )

    return CladeResponse(
        classifier=classifier,
        unit=unit,
        clicked=_taxon(clicked),
        anchor=_taxon(anchor),
        columns=columns,
        root=root,
        unplaced=unplaced_taxa(resolved, set(placed), names),
    )


def _classifier_entries(doc: dict, classifier: str) -> Optional[list[dict]]:
    """The profile entries for *classifier*, or None when there is no profile."""
    for profile in doc.get("profiles", []):
        if profile.get("classifier") == classifier:
            return list(profile.get("profile", []))
    return None


def _current_id(taxon_id: int, retired: dict[int, RetiredRecord]) -> int:
    """Resolve a clicked ID through ``taxa_retired``; deleted IDs cannot anchor."""
    record = retired.get(taxon_id)
    if record is None:
        return taxon_id
    if record.merged_into is None:
        raise HTTPException(
            status_code=404,
            detail=f"Taxon {taxon_id} was deleted from the NCBI taxonomy "
            "and cannot be placed",
        )
    return record.merged_into


async def _retired_records(
    db: AsyncIOMotorDatabase, taxon_ids: set[int]
) -> dict[int, RetiredRecord]:
    cursor = db["taxa_retired"].find(
        {"taxon_id": {"$in": list(taxon_ids)}},
        {"_id": 0, "taxon_id": 1, "status": 1, "merged_into": 1},
    )
    return {
        int(doc["taxon_id"]): RetiredRecord(
            status=doc["status"], merged_into=doc.get("merged_into")
        )
        async for doc in cursor
    }


async def _lineage_record(db: AsyncIOMotorDatabase, taxon_id: int) -> LineageRecord:
    """One taxon's lineage, or the HTTP error explaining why it has none.

    Ingest writes a placeholder ``taxa`` document (``taxdump_version`` None) for
    every profile ID the reference lacks, such as taxon 0 or IDs NCBI has since
    retired. A placeholder never gets a lineage, so it means "not in the
    taxonomy" — only a loaded document without ``ancestor_ids`` means the
    reference predates lineage support.
    """
    doc = await db["taxa"].find_one({"taxon_id": taxon_id}, _LINEAGE_PROJECTION)
    if doc is None or doc.get("taxdump_version") is None:
        raise HTTPException(
            status_code=404,
            detail=f"Taxon {taxon_id} is not in the loaded taxonomy reference",
        )
    if "ancestor_ids" not in doc:
        raise HTTPException(status_code=409, detail=TAXONOMY_REFRESH_DETAIL)
    if doc["ancestor_ids"] is None:
        raise HTTPException(
            status_code=404,
            detail=f"Taxon {taxon_id} has no lineage in the NCBI taxonomy",
        )
    return _to_record(doc)


async def _lineage_records(
    db: AsyncIOMotorDatabase, query: dict[str, Any]
) -> list[LineageRecord]:
    """Lineages matching *query*; documents without one are skipped.

    Skipped IDs are not lost: ``unplaced_taxa`` reports any profile ID without
    an array lineage, and a missing connector makes ``build_tree`` raise.
    """
    cursor = db["taxa"].find(
        {**query, "ancestor_ids": {"$type": "array"}}, _LINEAGE_PROJECTION
    )
    return [_to_record(doc) async for doc in cursor]


def _to_record(doc: dict) -> LineageRecord:
    return LineageRecord(
        taxon_id=int(doc["taxon_id"]),
        name=str(doc.get("name") or doc["taxon_id"]),
        rank=doc.get("rank"),
        ancestor_ids=[int(i) for i in doc["ancestor_ids"]],
    )


def _taxon(record: LineageRecord) -> CladeTaxon:
    return CladeTaxon(taxon_id=record.taxon_id, name=record.name, rank=record.rank)
