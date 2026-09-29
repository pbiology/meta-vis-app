# app/taxon_lists/rules.py
"""Pure validation of taxon-list entries against their list's kind."""

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping, Optional

from app.taxon_lists.kinds import (
    KIND_SPECS,
    MUTUALLY_EXCLUSIVE_KINDS,
    TaxonListKind,
)


def disallowed_fields(kind: TaxonListKind, provided: Mapping[str, object]) -> list[str]:
    """Kind-specific fields that were set but that *kind* does not accept.

    ``provided`` holds only the kind-specific fields the caller set, so a
    field left unset is never reported — only one sent to the wrong list.
    """
    allowed = KIND_SPECS[kind].extra_fields
    return sorted(name for name in provided if name not in allowed)


def nulled_fields(provided: Mapping[str, object]) -> list[str]:
    """Kind-specific fields explicitly set to null.

    Every kind-specific field carries a default, so null is never meaningful —
    it would leave e.g. a contaminant without the threshold its alert needs.
    """
    return sorted(name for name, value in provided.items() if value is None)


def with_defaults(
    kind: TaxonListKind, provided: Mapping[str, object]
) -> dict[str, object]:
    """The kind-specific fields for a new entry, defaults filled in."""
    return {**KIND_SPECS[kind].extra_fields, **provided}


def conflicting_kinds(
    kind: TaxonListKind, kinds_already_on: Iterable[TaxonListKind]
) -> set[TaxonListKind]:
    """Kinds the taxon is already on that forbid adding it to *kind*."""
    return {
        other
        for other in kinds_already_on
        if frozenset({kind, other}) in MUTUALLY_EXCLUSIVE_KINDS
    }


# ---------------------------------------------------------------------------
# Classifying taxa for addition — shared by single and bulk adds
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


RejectionReason = Literal["not_in_taxonomy", "merged", "deleted", "excluded_by_list"]


@dataclass(frozen=True)
class Rejection:
    taxon_id: int
    reason: RejectionReason
    detail: str
    merged_into: Optional[int] = None


@dataclass(frozen=True)
class Replacement:
    """A requested id NCBI merged into another, replaced by the current one."""

    taxon_id: int
    merged_into: int


@dataclass(frozen=True)
class Classification:
    """Every requested id lands in exactly one group — none is dropped:
    to add (directly or via its replacement), already on the list, or
    rejected. ``replacements`` annotates the merged ids that were replaced;
    ``to_add`` holds distinct taxa, so ids merged into one taxon add it once.
    """

    to_add: list[ResolvedTaxon]
    already_on_list: list[int]
    rejected: list[Rejection]
    replacements: list[Replacement]


def classify_taxa(
    kind: TaxonListKind,
    list_name: str,
    taxon_ids: Iterable[int],
    resolved: Mapping[int, ResolvedTaxon | RetiredTaxon],
    already_on: set[int],
    kinds_by_taxon: Mapping[int, set[TaxonListKind]],
) -> Classification:
    """Sort *taxon_ids* (de-duplicated, order kept) into add / skip / reject.

    A merged id is replaced by the id NCBI merged it into — there is no case
    for keeping a retired id — provided *resolved* holds that replacement as
    a current taxon; the replacement is then checked like any requested id.
    An id (or its replacement) already on the list is skipped whatever else
    is true of it: adding it again would change nothing.
    """
    to_add: list[ResolvedTaxon] = []
    scheduled: set[int] = set()
    already: list[int] = []
    rejected: list[Rejection] = []
    replacements: list[Replacement] = []
    for taxon_id in dict.fromkeys(taxon_ids):
        if taxon_id in already_on:
            already.append(taxon_id)
            continue
        target_id, found = taxon_id, resolved.get(taxon_id)
        if isinstance(found, RetiredTaxon) and found.merged_into is not None:
            current = resolved.get(found.merged_into)
            if isinstance(current, ResolvedTaxon):
                replacements.append(Replacement(taxon_id, found.merged_into))
                target_id, found = found.merged_into, current
                if target_id in already_on:
                    already.append(taxon_id)
                    continue

        conflicts = conflicting_kinds(kind, kinds_by_taxon.get(target_id, set()))
        if isinstance(found, RetiredTaxon):
            rejected.append(_retired(taxon_id, found))
        elif found is None:
            rejected.append(
                Rejection(
                    taxon_id,
                    "not_in_taxonomy",
                    f"Taxon {taxon_id} is not in the taxa collection. Check the ID, "
                    "or run load_taxonomy.py to populate reference data.",
                )
            )
        elif conflicts:
            rejected.append(
                Rejection(
                    taxon_id,
                    "excluded_by_list",
                    f"Taxon {target_id} is on a list of kind "
                    f"{', '.join(sorted(conflicts))}, which excludes {list_name!r}. "
                    "Remove it from there first.",
                )
            )
        elif target_id not in scheduled:
            scheduled.add(target_id)
            to_add.append(found)
    return Classification(to_add, already, rejected, replacements)


def _retired(taxon_id: int, retired: RetiredTaxon) -> Rejection:
    if retired.merged_into is not None:
        return Rejection(
            taxon_id,
            "merged",
            f"Taxon {taxon_id} was merged into {retired.merged_into} in the NCBI "
            f"taxonomy, which is not in the taxa collection either",
            merged_into=retired.merged_into,
        )
    return Rejection(
        taxon_id, "deleted", f"Taxon {taxon_id} was deleted from the NCBI taxonomy"
    )
