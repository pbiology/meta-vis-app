# tests/unit/test_taxon_list_rules.py
#
# Pure validation of taxon-list entries against their list's kind.

from app.taxon_lists import rules
from app.taxon_lists.kinds import KIND_SPECS, SYSTEM_LISTS, TaxonListKind


class TestKindRegistry:
    def test_every_kind_has_a_spec(self):
        assert set(KIND_SPECS) == set(TaxonListKind)

    def test_one_system_list_per_system_kind_with_unique_ids(self):
        system_kinds = [k for k in TaxonListKind if not KIND_SPECS[k].user_creatable]
        assert sorted(s.kind for s in SYSTEM_LISTS) == sorted(system_kinds)
        assert len({s.list_id for s in SYSTEM_LISTS}) == len(SYSTEM_LISTS)

    def test_display_filters_are_user_creatable_and_display_only(self):
        spec = KIND_SPECS[TaxonListKind.DISPLAY_FILTER]
        assert spec.user_creatable
        assert not spec.affects_analytics
        assert dict(spec.extra_fields) == {}


class TestDisallowedFields:
    def test_min_reads_accepted_on_contaminants(self):
        assert (
            rules.disallowed_fields(TaxonListKind.NTC_CONTAMINANTS, {"min_reads": 5})
            == []
        )

    def test_min_reads_rejected_elsewhere(self):
        for kind in (
            TaxonListKind.OUTBREAK_IGNORE,
            TaxonListKind.KNOWN_PATHOGENS,
            TaxonListKind.NTC_IGNORE,
        ):
            assert rules.disallowed_fields(kind, {"min_reads": 5}) == ["min_reads"]

    def test_unset_fields_are_never_reported(self):
        assert rules.disallowed_fields(TaxonListKind.NTC_IGNORE, {}) == []


class TestNulledFields:
    def test_reports_explicit_nulls(self):
        assert rules.nulled_fields({"min_reads": None}) == ["min_reads"]

    def test_values_pass(self):
        assert rules.nulled_fields({"min_reads": 0}) == []


class TestWithDefaults:
    def test_fills_in_missing_default(self):
        assert rules.with_defaults(TaxonListKind.NTC_CONTAMINANTS, {}) == {
            "min_reads": 3
        }

    def test_provided_value_wins(self):
        assert rules.with_defaults(
            TaxonListKind.NTC_CONTAMINANTS, {"min_reads": 10}
        ) == {"min_reads": 10}

    def test_kinds_without_extras_get_nothing(self):
        assert rules.with_defaults(TaxonListKind.KNOWN_PATHOGENS, {}) == {}


class TestConflictingKinds:
    def test_ntc_ignore_and_contaminants_exclude_each_other(self):
        assert rules.conflicting_kinds(
            TaxonListKind.NTC_IGNORE, {TaxonListKind.NTC_CONTAMINANTS}
        ) == {TaxonListKind.NTC_CONTAMINANTS}
        assert rules.conflicting_kinds(
            TaxonListKind.NTC_CONTAMINANTS, {TaxonListKind.NTC_IGNORE}
        ) == {TaxonListKind.NTC_IGNORE}

    def test_unrelated_kinds_do_not_conflict(self):
        assert (
            rules.conflicting_kinds(
                TaxonListKind.KNOWN_PATHOGENS,
                {TaxonListKind.OUTBREAK_IGNORE, TaxonListKind.NTC_IGNORE},
            )
            == set()
        )


class TestClassifyTaxa:
    RESOLVED = {
        1: rules.ResolvedTaxon(1, "A", "Bacteria"),
        2: rules.ResolvedTaxon(2, "B", "Viruses"),
        3: rules.RetiredTaxon("merged", 1),
        4: rules.RetiredTaxon("deleted", None),
        6: rules.RetiredTaxon("merged", 999),  # replacement not in the taxonomy
        7: rules.RetiredTaxon("merged", 2),
        8: rules.RetiredTaxon("merged", 2),
    }

    def _classify(self, ids, already_on=frozenset(), kinds=None, kind=None):
        return rules.classify_taxa(
            kind or TaxonListKind.DISPLAY_FILTER,
            "Skin flora",
            ids,
            self.RESOLVED,
            set(already_on),
            kinds or {},
        )

    def test_every_id_lands_in_exactly_one_group(self):
        result = self._classify([1, 2, 3, 4, 5], already_on={2})
        # 3 was merged into 1, which is already being added: one entry.
        assert [t.taxon_id for t in result.to_add] == [1]
        assert result.already_on_list == [2]
        assert [(r.taxon_id, r.merged_into) for r in result.replacements] == [(3, 1)]
        assert [(r.taxon_id, r.reason) for r in result.rejected] == [
            (4, "deleted"),
            (5, "not_in_taxonomy"),
        ]

    def test_merged_id_is_replaced_by_its_current_id(self):
        result = self._classify([7])
        assert [t.taxon_id for t in result.to_add] == [2]
        assert [(r.taxon_id, r.merged_into) for r in result.replacements] == [(7, 2)]

    def test_ids_merged_into_one_taxon_add_it_once(self):
        result = self._classify([7, 8])
        assert [t.taxon_id for t in result.to_add] == [2]
        assert len(result.replacements) == 2

    def test_replacement_already_on_the_list_is_skipped(self):
        result = self._classify([7], already_on={2})
        assert result.to_add == []
        assert result.already_on_list == [7]

    def test_replacement_is_checked_for_conflicting_lists(self):
        result = self._classify(
            [7],
            kinds={2: {TaxonListKind.NTC_CONTAMINANTS}},
            kind=TaxonListKind.NTC_IGNORE,
        )
        assert [(r.taxon_id, r.reason) for r in result.rejected] == [
            (7, "excluded_by_list")
        ]

    def test_merged_id_without_a_usable_replacement_is_rejected(self):
        (rejection,) = self._classify([6]).rejected
        assert rejection.reason == "merged"
        assert rejection.merged_into == 999

    def test_duplicates_are_collapsed_in_order(self):
        result = self._classify([2, 1, 2, 1])
        assert [t.taxon_id for t in result.to_add] == [2, 1]

    def test_already_on_list_wins_over_other_problems(self):
        result = self._classify([5], already_on={5})
        assert result.already_on_list == [5]
        assert result.rejected == []

    def test_exclusive_kinds_are_rejected_per_taxon(self):
        result = self._classify(
            [1, 2],
            kinds={1: {TaxonListKind.NTC_CONTAMINANTS}},
            kind=TaxonListKind.NTC_IGNORE,
        )
        assert [t.taxon_id for t in result.to_add] == [2]
        assert [(r.taxon_id, r.reason) for r in result.rejected] == [
            (1, "excluded_by_list")
        ]
