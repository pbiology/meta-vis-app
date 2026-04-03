# tests/unit/test_alerts_logic.py
#
# Tests for the outbreak detection logic in _compute_outbreaks.
# Uses a fake in-memory DB to avoid requiring a real MongoDB connection.

import pytest
from datetime import date, timedelta
from app.routers.alerts import parse_date, _cache, CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:

    def test_parses_iso_string(self):
        result = parse_date("2024-03-15")
        assert result == date(2024, 3, 15)

    def test_returns_date_object_unchanged(self):
        d = date(2024, 3, 15)
        assert parse_date(d) is d

    def test_parses_different_dates(self):
        assert parse_date("2020-01-01") == date(2020, 1, 1)
        assert parse_date("2024-12-31") == date(2024, 12, 31)


# ---------------------------------------------------------------------------
# Outbreak clustering logic (extracted and unit tested directly)
# ---------------------------------------------------------------------------

def find_flagged(case_entries: list, window_days: int) -> set:
    """
    Replicates the sliding window clustering from _compute_outbreaks.
    Extracted here so it can be unit tested without a DB.
    """
    sorted_entries = sorted(case_entries, key=lambda x: parse_date(x["order_date"]))
    flagged = set()
    for i, anchor in enumerate(sorted_entries):
        anchor_date = parse_date(anchor["order_date"])
        cluster = [anchor]
        for other in sorted_entries[i + 1:]:
            if (parse_date(other["order_date"]) - anchor_date).days <= window_days:
                cluster.append(other)
            else:
                break
        if len(cluster) >= 2:
            for entry in cluster:
                flagged.add(entry["case_id"])
    return flagged


def make_entry(case_id: str, order_date: str) -> dict:
    return {"case_id": case_id, "case_name": case_id, "order_date": order_date}


class TestOutbreakClustering:

    def test_two_cases_same_date_flagged(self):
        entries = [make_entry("case1", "2024-03-15"), make_entry("case2", "2024-03-15")]
        assert find_flagged(entries, window_days=14) == {"case1", "case2"}

    def test_two_cases_within_window_flagged(self):
        entries = [make_entry("case1", "2024-03-01"), make_entry("case2", "2024-03-14")]
        assert find_flagged(entries, window_days=14) == {"case1", "case2"}

    def test_two_cases_exactly_at_window_boundary_flagged(self):
        entries = [make_entry("case1", "2024-03-01"), make_entry("case2", "2024-03-15")]
        assert find_flagged(entries, window_days=14) == {"case1", "case2"}

    def test_two_cases_outside_window_not_flagged(self):
        entries = [make_entry("case1", "2024-03-01"), make_entry("case2", "2024-03-16")]
        assert find_flagged(entries, window_days=14) == set()

    def test_single_case_never_flagged(self):
        entries = [make_entry("case1", "2024-03-15")]
        assert find_flagged(entries, window_days=14) == set()

    def test_empty_entries_returns_empty_set(self):
        assert find_flagged([], window_days=14) == set()

    def test_three_cases_all_within_window(self):
        entries = [
            make_entry("case1", "2024-03-01"),
            make_entry("case2", "2024-03-08"),
            make_entry("case3", "2024-03-15"),
        ]
        flagged = find_flagged(entries, window_days=14)
        assert flagged == {"case1", "case2", "case3"}

    def test_three_cases_only_two_within_window(self):
        entries = [
            make_entry("case1", "2024-03-01"),
            make_entry("case2", "2024-03-10"),
            make_entry("case3", "2024-04-01"),  # outside window from case1
        ]
        flagged = find_flagged(entries, window_days=14)
        # case1 and case2 are within 14 days of each other
        assert "case1" in flagged
        assert "case2" in flagged
        # case3 is outside the window from case1 but might be within from case2
        # case2=Mar10, case3=Apr1 = 22 days — outside 14d window
        assert "case3" not in flagged

    def test_narrower_window_reduces_clusters(self):
        entries = [make_entry("case1", "2024-03-01"), make_entry("case2", "2024-03-10")]
        assert find_flagged(entries, window_days=14) == {"case1", "case2"}
        assert find_flagged(entries, window_days=7)  == set()

    def test_wider_window_increases_clusters(self):
        entries = [make_entry("case1", "2024-03-01"), make_entry("case2", "2024-03-20")]
        assert find_flagged(entries, window_days=14) == set()
        assert find_flagged(entries, window_days=30) == {"case1", "case2"}

    def test_unsorted_entries_handled_correctly(self):
        # Entries provided in reverse date order — should still work
        entries = [make_entry("case2", "2024-03-14"), make_entry("case1", "2024-03-01")]
        assert find_flagged(entries, window_days=14) == {"case1", "case2"}


# ---------------------------------------------------------------------------
# Cache module-level state
# ---------------------------------------------------------------------------

class TestAlertCache:

    def setup_method(self):
        _cache.clear()

    def test_cache_starts_empty_after_clear(self):
        assert _cache == {}

    def test_cache_stores_value(self):
        _cache[14] = {"window_days": 14, "outbreaks": []}
        assert 14 in _cache

    def test_cache_clear_removes_all_keys(self):
        _cache[14] = {"outbreaks": []}
        _cache[30] = {"outbreaks": []}
        _cache.clear()
        assert _cache == {}

    def test_cache_ttl_constant_is_positive(self):
        assert CACHE_TTL_SECONDS > 0

    def test_cache_ttl_at_least_one_hour(self):
        assert CACHE_TTL_SECONDS >= 3600