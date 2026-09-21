# tests/unit/test_ntc_controls.py
#
# The collapse rule on its own, with no database in the way: one physical
# control arrives as one sample document per case in its run, and these
# functions decide what the single collapsed control looks like.

from app.ntc_controls import (
    duplicated_analysis_ids,
    group_documents_by_control,
    pick_by_rank,
    resolve_controls,
)


def doc(
    sample_id: str = "NTC-A",
    case_id: str = "case-1",
    nucleic_acid: str = "DNA",
    order_date: str | None = "2026-08-07",
    analysis_id: str | None = None,
    ingested_at: str | None = None,
    **extra,
) -> dict:
    d: dict = {
        "sample_id": sample_id,
        "case_id": case_id,
        "nucleic_acid": nucleic_acid,
        "order_date": order_date,
    }
    if analysis_id is not None:
        d["analysis_id"] = analysis_id
    if ingested_at is not None:
        d["ingested_at"] = ingested_at
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# group_documents_by_control
# ---------------------------------------------------------------------------


class TestGrouping:
    def test_copies_of_one_control_group_together(self):
        groups = group_documents_by_control(
            [doc(case_id="case-1"), doc(case_id="case-2"), doc(case_id="case-3")]
        )

        assert list(groups) == [("NTC-A", "DNA")]
        assert len(groups[("NTC-A", "DNA")]) == 3

    def test_different_sample_ids_stay_apart(self):
        groups = group_documents_by_control([doc("NTC-A"), doc("NTC-B")])

        assert set(groups) == {("NTC-A", "DNA"), ("NTC-B", "DNA")}

    def test_dna_and_rna_aliquots_stay_apart(self):
        # The ids normally encode the nucleic acid; one that does not must not
        # have its two aliquots merged into a single point.
        groups = group_documents_by_control(
            [doc("NTC", nucleic_acid="DNA"), doc("NTC", nucleic_acid="RNA")]
        )

        assert set(groups) == {("NTC", "DNA"), ("NTC", "RNA")}


# ---------------------------------------------------------------------------
# duplicated_analysis_ids — the version lookup is skipped when nothing is tied
# ---------------------------------------------------------------------------


class TestDuplicatedAnalysisIds:
    def test_single_copy_controls_need_no_versions(self):
        groups = group_documents_by_control([doc("NTC-A", analysis_id="a1")])

        assert duplicated_analysis_ids(groups) == set()

    def test_shared_control_reports_every_copys_analysis(self):
        groups = group_documents_by_control(
            [
                doc(case_id="case-1", analysis_id="a1"),
                doc(case_id="case-2", analysis_id="a2"),
            ]
        )

        assert duplicated_analysis_ids(groups) == {"a1", "a2"}

    def test_copies_without_an_analysis_id_are_skipped(self):
        groups = group_documents_by_control(
            [doc(case_id="case-1", analysis_id="a1"), doc(case_id="case-2")]
        )

        assert duplicated_analysis_ids(groups) == {"a1"}


# ---------------------------------------------------------------------------
# resolve_controls
# ---------------------------------------------------------------------------


class TestResolveControls:
    def test_one_control_out_of_many_copies(self):
        controls = resolve_controls(
            group_documents_by_control([doc(case_id="case-1"), doc(case_id="case-2")]),
            {},
        )

        assert len(controls) == 1

    def test_date_is_the_earliest_across_copies(self):
        # Copies agree once a control carries its own date. On older data they
        # do not, and the earliest is the only date that cannot shift as
        # further analyses arrive.
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="case-1", order_date="2026-09-03"),
                    doc(case_id="case-2", order_date="2026-07-15"),
                ]
            ),
            {},
        )

        assert controls[("NTC-A", "DNA")].order_date == "2026-07-15"

    def test_date_is_none_when_no_copy_has_one(self):
        controls = resolve_controls(
            group_documents_by_control([doc(order_date=None)]), {}
        )

        assert controls[("NTC-A", "DNA")].order_date is None

    def test_missing_dates_do_not_hide_a_present_one(self):
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="case-1", order_date=None),
                    doc(case_id="case-2", order_date="2026-08-07"),
                ]
            ),
            {},
        )

        assert controls[("NTC-A", "DNA")].order_date == "2026-08-07"

    def test_highest_version_wins(self):
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="case-1", analysis_id="a1", reads=1),
                    doc(case_id="case-2", analysis_id="a2", reads=2),
                ]
            ),
            {"a1": 1, "a2": 3},
        )

        assert controls[("NTC-A", "DNA")].winner["reads"] == 2

    def test_ingested_at_breaks_a_version_tie(self):
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="case-1", ingested_at="2026-09-07 11:53:46", reads=1),
                    doc(case_id="case-2", ingested_at="2026-09-17 08:26:04", reads=2),
                ]
            ),
            {},
        )

        assert controls[("NTC-A", "DNA")].winner["reads"] == 2

    def test_case_id_breaks_a_full_tie_so_the_result_is_reproducible(self):
        copies = [doc(case_id="zulu", reads=1), doc(case_id="alpha", reads=2)]

        first = resolve_controls(group_documents_by_control(copies), {})
        second = resolve_controls(group_documents_by_control(copies[::-1]), {})

        assert first[("NTC-A", "DNA")].winner["reads"] == 2
        assert second[("NTC-A", "DNA")].winner["reads"] == 2

    def test_a_copy_without_a_version_ranks_below_one_with(self):
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="case-1", reads=1),
                    doc(case_id="case-2", analysis_id="a2", reads=2),
                ]
            ),
            {"a2": 1},
        )

        assert controls[("NTC-A", "DNA")].winner["reads"] == 2

    def test_case_ids_are_ranked_newest_first(self):
        controls = resolve_controls(
            group_documents_by_control(
                [
                    doc(case_id="older", analysis_id="a1"),
                    doc(case_id="newest", analysis_id="a2"),
                ]
            ),
            {"a1": 1, "a2": 5},
        )

        assert controls[("NTC-A", "DNA")].case_ids == ("newest", "older")


# ---------------------------------------------------------------------------
# pick_by_rank
# ---------------------------------------------------------------------------


class TestPickByRank:
    def _control(self, versions: dict[str, int]):
        copies = [
            doc(case_id="case-old", analysis_id="a1"),
            doc(case_id="case-new", analysis_id="a2"),
        ]
        controls = resolve_controls(group_documents_by_control(copies), versions)
        return controls[("NTC-A", "DNA")]

    def test_the_newest_case_wins(self):
        control = self._control({"a1": 1, "a2": 5})

        assert pick_by_rank(control, {"case-old": "old", "case-new": "new"}) == "new"

    def test_falls_back_when_the_newest_case_has_nothing(self):
        control = self._control({"a1": 1, "a2": 5})

        assert pick_by_rank(control, {"case-old": "old"}) == "old"

    def test_returns_none_when_no_case_has_anything(self):
        control = self._control({"a1": 1, "a2": 5})

        assert pick_by_rank(control, {}) is None
