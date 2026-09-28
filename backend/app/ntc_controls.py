# app/ntc_controls.py
"""Collapse NTC sample documents into the physical controls they describe.

A negative control belongs to a batch, and a case is one patient's samples plus
the controls of their batch. So one control reaches the database as one
`samples` document per case in its batch, all sharing a `sample_id`. Anything
that counts or plots controls — the NTC trends page — must count the control,
not the documents; otherwise a control shared by seven cases is reported as
seven controls and inflates both sides of the recurring-taxon threshold.

The `sample_id` is the only thing that identifies the control across cases: the
app records no batch. A lab that reuses one name for every batch's control
therefore merges all of them into a single control here, which collapses the
trend charts and makes every taxon look recurrent. Unique control names per
batch are an ingest convention (see docs/user-guide/loading-data.rst).

Two rules decide what a collapsed control looks like:

* **Its date is the earliest order date of its cases.** A control has no order
  of its own; each copy carries the order date of the case it was uploaded
  with. Cases of one batch share that date, so copies normally agree. When a
  control ends up in two orders, the earliest date is used — and taking the
  minimum rather than the winning document's date stops the point jumping when
  a new analysis arrives.
* **Its values come from the newest sequencing.** Where copies could disagree,
  the document from the highest analysis version wins. Documents are ranked
  rather than merged, so a caller can fall back down the ranking for a value
  the winner happens to lack.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# (sample_id, nucleic_acid). The sample_id is the control's identity — see the
# module docstring for what a name reused across batches does. Pairing it with
# the nucleic acid costs nothing and keeps a control whose name does not encode
# it from merging its DNA and RNA aliquots into one point.
ControlKey = tuple[str, str]


@dataclass(frozen=True)
class NtcControl:
    """One physical negative control, collapsed from its sample documents."""

    sample_id: str
    nucleic_acid: str
    # Minimum order_date across the copies; None only when no copy has one.
    order_date: str | None
    # Every document for this control, newest sequencing first. Kept whole
    # rather than reduced to the winner so a caller can walk down the ranking
    # for a value the newest copy happens to lack.
    copies: tuple[Mapping[str, Any], ...]

    @property
    def winner(self) -> Mapping[str, Any]:
        """The document from the newest analysis: the one whose values win."""
        return self.copies[0]

    @property
    def case_ids(self) -> tuple[str, ...]:
        """The cases this control was sequenced alongside, in ranked order."""
        return tuple(str(doc.get("case_id") or "") for doc in self.copies)


def group_documents_by_control(
    docs: Iterable[Mapping[str, Any]],
) -> dict[ControlKey, list[Mapping[str, Any]]]:
    """Bucket NTC sample documents by the control they belong to.

    Kept separate from :func:`resolve_controls` so a caller can see which
    controls actually have several copies and skip looking up analysis versions
    when none do.
    """
    groups: dict[ControlKey, list[Mapping[str, Any]]] = {}
    for doc in docs:
        key = (str(doc["sample_id"]), str(doc.get("nucleic_acid") or ""))
        groups.setdefault(key, []).append(doc)
    return groups


def duplicated_analysis_ids(
    groups: Mapping[ControlKey, list[Mapping[str, Any]]],
) -> set[str]:
    """Analysis ids of documents belonging to controls with more than one copy.

    Only these need a version lookup: a control with a single document has
    nothing to rank.
    """
    return {
        str(doc["analysis_id"])
        for copies in groups.values()
        if len(copies) > 1
        for doc in copies
        if doc.get("analysis_id") is not None
    }


def resolve_controls(
    groups: Mapping[ControlKey, list[Mapping[str, Any]]],
    version_by_analysis: Mapping[str, int],
) -> dict[ControlKey, NtcControl]:
    """Collapse each group of copies into one :class:`NtcControl`."""
    return {
        key: _resolve_one(key, copies, version_by_analysis)
        for key, copies in groups.items()
    }


def _resolve_one(
    key: ControlKey,
    copies: list[Mapping[str, Any]],
    version_by_analysis: Mapping[str, int],
) -> NtcControl:
    ranked = _rank_copies(copies, version_by_analysis)
    dates = sorted(str(doc["order_date"]) for doc in copies if doc.get("order_date"))
    sample_id, nucleic_acid = key
    return NtcControl(
        sample_id=sample_id,
        nucleic_acid=nucleic_acid,
        order_date=dates[0] if dates else None,
        copies=tuple(ranked),
    )


def _rank_copies(
    copies: list[Mapping[str, Any]], version_by_analysis: Mapping[str, int]
) -> list[Mapping[str, Any]]:
    """Order a control's copies newest sequencing first.

    Highest analysis version wins, because that is what "re-sequenced" means
    for a case. Versions are per case, so copies from different cases are
    routinely tied — `ingested_at` then `case_id` break the tie so the result
    is reproducible rather than dependent on the order Mongo returned.
    """
    # Applied in reverse order of significance: Python's sort is stable, so the
    # ascending case_id pass survives inside the descending pass above it.
    ranked = sorted(copies, key=lambda doc: str(doc.get("case_id") or ""))
    ranked.sort(
        key=lambda doc: (
            version_by_analysis.get(str(doc.get("analysis_id")), 0),
            _ingested_at_key(doc),
        ),
        reverse=True,
    )
    return ranked


def _ingested_at_key(doc: Mapping[str, Any]) -> str:
    """`ingested_at` as a sortable string.

    Compared as text rather than as datetimes: the values come back from Mongo
    naive, and a tz-aware one would raise on comparison against the empty
    fallback a document without the field needs.
    """
    ingested_at = doc.get("ingested_at")
    return str(ingested_at) if ingested_at is not None else ""


def pick_by_rank(control: NtcControl, by_case_id: Mapping[str, Any]) -> Any | None:
    """Return the value from the newest case of `control` that has one.

    The winner is preferred, but a value it lacks — a taxon below threshold in
    that run, a kingdom tally from a document with no usable profile — is taken
    from the next-newest copy rather than reported as missing.
    """
    for case_id in control.case_ids:
        if case_id in by_case_id:
            return by_case_id[case_id]
    return None
