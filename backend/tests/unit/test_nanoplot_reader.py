# tests/unit/test_nanoplot_reader.py

import textwrap
import pytest
from app.ingestor.nanoplot_reader import read_nanostats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_stats(tmp_path, content: str, filename: str = "NanoStats.txt"):
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return str(p)


FULL_STATS = """\
    General summary:
    Mean read length:              1,520.6
    Mean read quality:                15.8
    Median read length:            1,563.0
    Median read quality:              17.9
    Number of reads:               5,000.0
    Read length N50:               1,564.0
    STDEV read length:               251.8
    Total bases:               7,602,885.0
    Number, percentage and megabases of reads above quality cutoffs
    >Q10:\t4765 (95.3%) 7.2Mb
    >Q15:\t4229 (84.6%) 6.5Mb
"""

PARTIAL_STATS = """\
    General summary:
    Mean read length:              1,520.6
    Number of reads:               5,000.0
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadNanostats:
    def test_happy_path(self, tmp_path):
        path = write_stats(tmp_path, FULL_STATS)
        stats = read_nanostats(path)

        assert stats.mean_read_length == pytest.approx(1520.6)
        assert stats.mean_read_quality == pytest.approx(15.8)
        assert stats.median_read_length == pytest.approx(1563.0)
        assert stats.median_read_quality == pytest.approx(17.9)
        assert stats.number_of_reads == 5000
        assert stats.read_length_n50 == 1564
        assert stats.total_bases == 7602885

    def test_partial_file(self, tmp_path):
        path = write_stats(tmp_path, PARTIAL_STATS)
        stats = read_nanostats(path)

        assert stats.mean_read_length == pytest.approx(1520.6)
        assert stats.number_of_reads == 5000
        assert stats.mean_read_quality is None
        assert stats.median_read_length is None
        assert stats.read_length_n50 is None

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="NanoStats file not found"):
            read_nanostats(str(tmp_path / "nonexistent.txt"))

    def test_empty_file(self, tmp_path):
        path = write_stats(tmp_path, "")
        stats = read_nanostats(path)

        assert stats.mean_read_length is None
        assert stats.number_of_reads is None
