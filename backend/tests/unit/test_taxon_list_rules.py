# tests/unit/test_taxon_list_rules.py
#
# Pure validation of taxon-list entries against their list's kind.

from app.taxon_lists import rules
from app.taxon_lists.kinds import KIND_SPECS, SYSTEM_LISTS, TaxonListKind


class TestKindRegistry:
    def test_every_kind_has_a_spec(self):
        assert set(KIND_SPECS) == set(TaxonListKind)

    def test_one_system_list_per_kind_with_unique_ids(self):
        assert sorted(s.kind for s in SYSTEM_LISTS) == sorted(TaxonListKind)
        assert len({s.list_id for s in SYSTEM_LISTS}) == len(SYSTEM_LISTS)


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
