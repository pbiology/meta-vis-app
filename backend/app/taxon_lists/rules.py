# app/taxon_lists/rules.py
"""Pure validation of taxon-list entries against their list's kind."""

from typing import Iterable, Mapping

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
