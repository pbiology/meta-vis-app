# tests/unit/test_clade_tree.py

import pytest

from app.clade.tree import (
    LineageRecord,
    ResolvedSignal,
    RetiredRecord,
    build_tree,
    column_signal,
    connector_ids,
    pick_anchor_id,
    resolve_retired,
    unplaced_taxa,
)


# ---------------------------------------------------------------------------
# Helpers — a slice of the real NCBI lineage for Escherichia
# ---------------------------------------------------------------------------

ABOVE_FAMILY = [131567, 2, 3379134, 1224, 1236, 91347]


def rec(taxon_id: int, name: str, rank: str | None, *ancestors: int) -> LineageRecord:
    return LineageRecord(
        taxon_id=taxon_id,
        name=name,
        rank=rank,
        ancestor_ids=[*ABOVE_FAMILY, *ancestors],
    )


ENTEROBACTERIACEAE = rec(543, "Enterobacteriaceae", "family")
ESCHERICHIA = rec(561, "Escherichia", "genus", 543)
E_COLI = rec(562, "Escherichia coli", "species", 543, 561)
K12 = rec(83333, "Escherichia coli K-12", "strain", 543, 561, 562)
O157 = rec(83334, "Escherichia coli O157:H7", "serotype", 543, 561, 562)
E_ALBERTII = rec(208962, "Escherichia albertii", "species", 543, 561)
SHIGELLA = rec(620, "Shigella", "genus", 543)


def records(*recs: LineageRecord) -> dict[int, LineageRecord]:
    return {r.taxon_id: r for r in recs}


def resolved(**columns: dict[int, float]) -> ResolvedSignal:
    return ResolvedSignal(values=dict(columns))


def child(node, taxon_id):
    return next(c for c in node.children if c.taxon_id == taxon_id)


# ---------------------------------------------------------------------------
# column_signal
# ---------------------------------------------------------------------------


def test_column_signal_counts_unclassified_in_total_only():
    signal, total = column_signal(
        [
            {"taxon_id": 0, "abundance": 900},
            {"taxon_id": 562, "abundance": 100},
        ]
    )

    assert signal == {562: 100.0}
    assert total == 1000.0


def test_column_signal_sums_a_taxon_listed_twice():
    signal, _ = column_signal(
        [{"taxon_id": 562, "abundance": 10}, {"taxon_id": 562, "abundance": 5}]
    )

    assert signal == {562: 15.0}


def test_column_signal_drops_zero_abundance():
    signal, _ = column_signal([{"taxon_id": 562, "abundance": 0}])

    assert signal == {}


# ---------------------------------------------------------------------------
# resolve_retired
# ---------------------------------------------------------------------------


def test_resolve_retired_adds_merged_signal_to_current_id():
    retired = {12: RetiredRecord(status="merged", merged_into=562)}

    result = resolve_retired({"S1": {12: 4.0, 562: 10.0}}, retired)

    assert result.values == {"S1": {562: 14.0}}
    assert result.merged_from == {562: {12}}


def test_resolve_retired_sets_deleted_ids_aside():
    retired = {99: RetiredRecord(status="deleted", merged_into=None)}

    result = resolve_retired({"S1": {99: 3.0}, "NTC": {99: 1.0}}, retired)

    assert result.values == {"S1": {}, "NTC": {}}
    assert result.deleted == {99: {"S1": 3.0, "NTC": 1.0}}


def test_resolve_retired_leaves_current_ids_untouched():
    result = resolve_retired({"S1": {562: 10.0}}, {})

    assert result.values == {"S1": {562: 10.0}}
    assert result.merged_from == {}
    assert result.deleted == {}


# ---------------------------------------------------------------------------
# pick_anchor_id
# ---------------------------------------------------------------------------


def test_pick_anchor_id_uses_genus_ancestor():
    assert pick_anchor_id(K12, 561) == 561


def test_pick_anchor_id_falls_back_to_clicked_taxon():
    assert pick_anchor_id(ENTEROBACTERIACEAE, None) == 543


# ---------------------------------------------------------------------------
# connector_ids
# ---------------------------------------------------------------------------


def test_connector_ids_finds_species_between_genus_and_strains():
    assert connector_ids(561, [ESCHERICHIA, K12, O157]) == {562}


def test_connector_ids_empty_when_parents_present():
    assert connector_ids(561, [ESCHERICHIA, E_COLI, K12]) == set()


# ---------------------------------------------------------------------------
# build_tree
# ---------------------------------------------------------------------------


def test_build_tree_nests_under_anchor():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI, K12, O157, E_ALBERTII),
        resolved(S1={83333: 5.0, 83334: 3.0, 208962: 1.0}),
        {"S1": None},
        "S1",
    )

    assert root.taxon_id == 561
    assert [c.taxon_id for c in root.children] == [562, 208962]
    assert {c.taxon_id for c in child(root, 562).children} == {83333, 83334}


def test_build_tree_sums_clade_from_direct_signal():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI, K12, O157),
        resolved(S1={561: 2.0, 562: 10.0, 83333: 5.0, 83334: 3.0}),
        {"S1": None},
        "S1",
    )

    assert root.cells["S1"].direct == 2.0
    assert root.cells["S1"].clade == 20.0
    assert child(root, 562).cells["S1"].direct == 10.0
    assert child(root, 562).cells["S1"].clade == 18.0


def test_build_tree_marks_nodes_without_direct_signal_as_connectors():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI, K12),
        resolved(S1={83333: 5.0}, NTC={83333: 1.0}),
        {"S1": None, "NTC": None},
        "S1",
    )

    assert root.is_connector
    assert child(root, 562).is_connector
    assert not child(child(root, 562), 83333).is_connector


def test_build_tree_shows_taxon_found_only_in_control():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI, K12, O157),
        resolved(S1={83334: 5.0}, NTC={83333: 2.0}),
        {"S1": None, "NTC": None},
        "S1",
    )

    k12 = child(child(root, 562), 83333)
    assert k12.cells["S1"].direct == 0.0
    assert k12.cells["NTC"].direct == 2.0
    assert not k12.is_connector


def test_build_tree_computes_reads_per_million_per_column():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI),
        resolved(S1={562: 50.0}, NTC={562: 2.0}),
        {"S1": 1_000_000.0, "NTC": 4_000.0},
        "S1",
    )

    e_coli = child(root, 562)
    assert e_coli.cells["S1"].direct_rpm == 50.0
    assert e_coli.cells["NTC"].direct_rpm == 500.0
    assert root.cells["NTC"].clade_rpm == 500.0
    assert root.cells["NTC"].direct_rpm == 0.0


@pytest.mark.parametrize("total", [None, 0.0])
def test_build_tree_has_no_rpm_without_a_usable_total(total):
    root = build_tree(
        561, records(ESCHERICHIA), resolved(S1={561: 0.4}), {"S1": total}, "S1"
    )

    assert root.cells["S1"].direct_rpm is None
    assert root.cells["S1"].clade_rpm is None


def test_build_tree_gives_no_cells_to_column_without_profile():
    root = build_tree(
        561, records(ESCHERICHIA), resolved(S1={561: 3.0}), {"S1": None}, "S1"
    )

    assert set(root.cells) == {"S1"}


def test_build_tree_orders_children_by_sample_then_control_signal():
    root = build_tree(
        561,
        records(ESCHERICHIA, E_COLI, E_ALBERTII),
        resolved(S1={562: 1.0, 208962: 1.0}, NTC={208962: 9.0}),
        {"S1": None, "NTC": None},
        "S1",
    )

    assert [c.taxon_id for c in root.children] == [208962, 562]


def test_build_tree_lists_merged_ids_on_node():
    signal = ResolvedSignal(values={"S1": {562: 14.0}}, merged_from={562: {12}})

    root = build_tree(561, records(ESCHERICHIA, E_COLI), signal, {"S1": None}, "S1")

    assert child(root, 562).merged_from == [12]


def test_build_tree_raises_when_parent_missing():
    with pytest.raises(ValueError, match="Parent 562 of taxon 83333"):
        build_tree(561, records(ESCHERICHIA, K12), resolved(S1={}), {"S1": None}, "S1")


def test_build_tree_raises_for_record_outside_anchor():
    with pytest.raises(ValueError, match="not below anchor 561"):
        build_tree(
            561, records(ESCHERICHIA, SHIGELLA), resolved(S1={}), {"S1": None}, "S1"
        )


# ---------------------------------------------------------------------------
# unplaced_taxa
# ---------------------------------------------------------------------------


def test_unplaced_taxa_reports_deleted_ids():
    signal = ResolvedSignal(values={"S1": {}}, deleted={99: {"S1": 3.0}})

    result = unplaced_taxa(signal, set(), {99: "old taxon"})

    assert len(result) == 1
    assert result[0].taxon_id == 99
    assert result[0].reason == "deleted"
    assert result[0].name == "old taxon"
    assert result[0].cells["S1"].direct == 3.0


def test_unplaced_taxa_reports_ids_without_lineage():
    result = unplaced_taxa(resolved(S1={562: 1.0, 777: 2.0}), {562}, {})

    assert [(u.taxon_id, u.reason) for u in result] == [(777, "not_in_taxonomy")]


def test_unplaced_taxa_names_merge_target_after_merged_id():
    signal = ResolvedSignal(
        values={"S1": {777: 6.0}, "NTC": {777: 1.0}}, merged_from={777: {12}}
    )

    result = unplaced_taxa(signal, set(), {12: "name in classifier db"})

    assert len(result) == 1
    assert result[0].taxon_id == 777
    assert result[0].merged_from == [12]
    assert result[0].name == "name in classifier db"
    assert result[0].cells["S1"].direct == 6.0
    assert result[0].cells["NTC"].direct == 1.0
