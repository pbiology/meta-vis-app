# app/clade/tree.py
"""Pure clade-building logic: turns profiles plus taxonomy records into a tree.

No database or FastAPI here, so every rule is unit-testable with inline data.
``app.clade.loader`` fetches the inputs and calls these functions in order:

1. ``column_signal``     — one profile → direct signal per taxon, plus total
2. ``resolve_retired``   — move signal on merged IDs to their current ID
3. ``pick_anchor_id``    — the clicked taxon's genus, or the taxon itself
4. ``connector_ids``     — taxa with no signal needed to connect the tree
5. ``build_tree``        — nest, sum clade totals, compute reads-per-million
6. ``unplaced_taxa``     — signal that could not be placed anywhere
"""

from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

from app.models.clade import CladeCell, CladeNode, UnplacedReason, UnplacedTaxon

# Kraken2 reports unassigned reads on taxon 0. It counts toward the classifier
# total but is not a taxon, so it never becomes a tree node.
UNCLASSIFIED_TAXON_ID = 0


@dataclass(frozen=True)
class LineageRecord:
    """The fields of a ``taxa`` document the tree needs."""

    taxon_id: int
    name: str
    rank: Optional[str]
    # Outermost first, excluding root and the taxon itself (NCBI layout).
    ancestor_ids: list[int]


@dataclass(frozen=True)
class RetiredRecord:
    """One ``taxa_retired`` document."""

    status: Literal["merged", "deleted"]
    merged_into: Optional[int]


@dataclass
class ResolvedSignal:
    """Signal per column after merged IDs are mapped to their current ID."""

    # sample_id → current taxon_id → direct signal
    values: dict[str, dict[int, float]]
    # current taxon_id → retired IDs whose signal was added to it
    merged_from: dict[int, set[int]] = field(default_factory=dict)
    # deleted taxon_id → sample_id → direct signal
    deleted: dict[int, dict[str, float]] = field(default_factory=dict)


def column_signal(entries: Iterable[dict]) -> tuple[dict[int, float], float]:
    """Direct signal per taxon for one profile, and the profile's total.

    The total includes unclassified signal: it is the reads-per-million
    denominator, and a sample that is mostly unclassified must not look
    enriched. A taxon listed twice is summed rather than overwritten.
    """
    signal: dict[int, float] = {}
    total = 0.0
    for entry in entries:
        value = float(entry["abundance"])
        total += value
        taxon_id = int(entry["taxon_id"])
        if taxon_id == UNCLASSIFIED_TAXON_ID or value <= 0:
            continue
        signal[taxon_id] = signal.get(taxon_id, 0.0) + value
    return signal, total


def resolve_retired(
    signal: dict[str, dict[int, float]], retired: dict[int, RetiredRecord]
) -> ResolvedSignal:
    """Map merged IDs onto their current ID and set deleted IDs aside.

    A profile can carry both an old ID and the ID it was merged into — the
    classifier database predates the merge — so signal is added, not replaced.
    """
    resolved = ResolvedSignal(values={sample_id: {} for sample_id in signal})
    for sample_id, per_taxon in signal.items():
        target = resolved.values[sample_id]
        for taxon_id, value in per_taxon.items():
            record = retired.get(taxon_id)
            if record is None:
                target[taxon_id] = target.get(taxon_id, 0.0) + value
            elif record.status == "deleted" or record.merged_into is None:
                resolved.deleted.setdefault(taxon_id, {})[sample_id] = value
            else:
                current = record.merged_into
                target[current] = target.get(current, 0.0) + value
                resolved.merged_from.setdefault(current, set()).add(taxon_id)
    return resolved


def pick_anchor_id(clicked: LineageRecord, genus_ancestor_id: Optional[int]) -> int:
    """The tree root: the clicked taxon's genus, if it has one.

    Strain and species differences are the point of the view, so clicking
    E. coli opens Escherichia. A taxon at genus or above, or one without a
    genus ancestor (common for viruses), is its own anchor.
    """
    return genus_ancestor_id if genus_ancestor_id is not None else clicked.taxon_id


def connector_ids(anchor_id: int, members: Iterable[LineageRecord]) -> set[int]:
    """IDs between the anchor and a member that are not members themselves.

    Kraken2 counts are direct, so a species with no reads of its own can sit
    between the genus and the strains that do. Without it the tree breaks.
    """
    members = list(members)
    member_ids = {m.taxon_id for m in members}
    needed: set[int] = set()
    for member in members:
        if member.taxon_id == anchor_id:
            continue
        path = _path_below_anchor(member, anchor_id)
        needed.update(taxon_id for taxon_id in path if taxon_id not in member_ids)
    return needed


def build_tree(
    anchor_id: int,
    records: dict[int, LineageRecord],
    resolved: ResolvedSignal,
    totals: dict[str, Optional[float]],
    sample_column: str,
) -> CladeNode:
    """Nest *records* under the anchor and fill in per-column cells.

    *records* must hold the anchor, every member and every connector. A parent
    missing from it means the taxonomy was loaded inconsistently; that raises
    rather than silently hanging the subtree off somewhere else.

    *totals* maps each column with a profile to its reads-per-million
    denominator (None when the unit has no RPM). Columns absent from *totals*
    get no cells at all. Children are ordered by the sample's clade signal,
    then the highest control's, then name.
    """
    if anchor_id not in records:
        raise ValueError(f"Anchor taxon {anchor_id} is missing from the records")

    children_of: dict[int, list[int]] = {}
    for taxon_id, record in records.items():
        if taxon_id == anchor_id:
            continue
        _path_below_anchor(record, anchor_id)  # raises if not under the anchor
        parent_id = record.ancestor_ids[-1]
        if parent_id not in records:
            raise ValueError(
                f"Parent {parent_id} of taxon {taxon_id} is missing from the records"
            )
        children_of.setdefault(parent_id, []).append(taxon_id)

    return _build_node(anchor_id, records, children_of, resolved, totals, sample_column)


def unplaced_taxa(
    resolved: ResolvedSignal, placed_ids: set[int], names: dict[int, str]
) -> list[UnplacedTaxon]:
    """Signal that cannot be put in any tree, ordered by taxon ID.

    Deleted IDs, and current IDs (including merge targets) with no placeable
    taxonomy record. Reported for the whole analysis because, without a
    lineage, there is no way to tell whether they belong to the clade viewed.
    *names* comes from the profiles; a merge target the classifier database
    never knew falls back to the name of an ID merged into it.
    """
    unplaced = [
        _unplaced(taxon_id, names.get(taxon_id), "deleted", [], per_column)
        for taxon_id, per_column in resolved.deleted.items()
    ]

    unplaceable: dict[int, dict[str, float]] = {}
    for sample_id, per_taxon in resolved.values.items():
        for taxon_id, value in per_taxon.items():
            if taxon_id not in placed_ids:
                unplaceable.setdefault(taxon_id, {})[sample_id] = value
    for taxon_id, per_column in unplaceable.items():
        merged_from = sorted(resolved.merged_from.get(taxon_id, ()))
        name = names.get(taxon_id) or next(
            (names[old] for old in merged_from if old in names), None
        )
        unplaced.append(
            _unplaced(taxon_id, name, "not_in_taxonomy", merged_from, per_column)
        )

    return sorted(unplaced, key=lambda u: u.taxon_id)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _path_below_anchor(record: LineageRecord, anchor_id: int) -> list[int]:
    """Ancestor IDs strictly between the anchor and *record*."""
    try:
        index = record.ancestor_ids.index(anchor_id)
    except ValueError:
        raise ValueError(
            f"Taxon {record.taxon_id} is not below anchor {anchor_id}"
        ) from None
    return record.ancestor_ids[index + 1 :]


def _rpm(value: float, total: Optional[float]) -> Optional[float]:
    if total is None or total <= 0:
        return None
    return value / total * 1_000_000


def _build_node(
    taxon_id: int,
    records: dict[int, LineageRecord],
    children_of: dict[int, list[int]],
    resolved: ResolvedSignal,
    totals: dict[str, Optional[float]],
    sample_column: str,
) -> CladeNode:
    children = [
        _build_node(child_id, records, children_of, resolved, totals, sample_column)
        for child_id in children_of.get(taxon_id, [])
    ]
    children.sort(key=lambda child: _sort_key(child, sample_column))

    cells: dict[str, CladeCell] = {}
    for sample_id, total in totals.items():
        direct = resolved.values.get(sample_id, {}).get(taxon_id, 0.0)
        clade = direct + sum(
            child.cells[sample_id].clade
            for child in children
            if sample_id in child.cells
        )
        cells[sample_id] = CladeCell(
            direct=direct,
            clade=clade,
            direct_rpm=_rpm(direct, total),
            clade_rpm=_rpm(clade, total),
        )

    record = records[taxon_id]
    return CladeNode(
        taxon_id=taxon_id,
        name=record.name,
        rank=record.rank,
        cells=cells,
        is_connector=all(cell.direct == 0 for cell in cells.values()),
        merged_from=sorted(resolved.merged_from.get(taxon_id, ())),
        children=children,
    )


def _sort_key(node: CladeNode, sample_column: str) -> tuple[float, float, str]:
    sample_cell = node.cells.get(sample_column)
    sample_clade = sample_cell.clade if sample_cell else 0.0
    control_clade = max(
        (cell.clade for sid, cell in node.cells.items() if sid != sample_column),
        default=0.0,
    )
    return (-sample_clade, -control_clade, node.name)


def _unplaced(
    taxon_id: int,
    name: Optional[str],
    reason: UnplacedReason,
    merged_from: list[int],
    per_column: dict[str, float],
) -> UnplacedTaxon:
    return UnplacedTaxon(
        taxon_id=taxon_id,
        name=name,
        reason=reason,
        merged_from=merged_from,
        cells={
            sample_id: CladeCell(direct=value, clade=value)
            for sample_id, value in per_column.items()
        },
    )
