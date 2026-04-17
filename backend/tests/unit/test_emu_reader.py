# tests/unit/test_emu_reader.py

import textwrap
import pytest
from app.ingestor.emu_reader import read_emu_abundance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_tsv(tmp_path, content: str, filename: str = "emu.tsv"):
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return str(p)


MINIMAL_TSV = """\
    tax_id\tabundance\tspecies\tgenus\tfamily\torder\tclass\tphylum\tclade\tsuperkingdom\testimated counts
    853\t0.2\tFaecalibacterium prausnitzii\tFaecalibacterium\tRuminococcaceae\tClostridiales\tClostridia\tFirmicutes\tTerrabacteria group\tBacteria\t200.0
    562\t0.11\tEscherichia coli\tEscherichia\tEnterobacteriaceae\tEnterobacterales\tGammaproteobacteria\tProteobacteria\t\tBacteria\t110.0
    unmapped\t0.0\t\t\t\t\t\t\t\t\t0.0
    mapped_unclassified\t0.0\t\t\t\t\t\t\t\t\t0.0
"""

ZERO_ABUNDANCE_TSV = """\
    tax_id\tabundance\tspecies\tgenus\tsuperkingdom
    853\t0.0\tFaecalibacterium prausnitzii\tFaecalibacterium\tBacteria
    562\t0.0\tEscherichia coli\tEscherichia\tBacteria
"""

NO_SPECIES_TSV = """\
    tax_id\tabundance\tgenus\tfamily\tsuperkingdom
    1279\t0.15\tStaphylococcus\tStaphylococcaceae\tBacteria
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadEmuAbundance:
    def test_happy_path(self, tmp_path):
        path = write_tsv(tmp_path, MINIMAL_TSV)
        entries = read_emu_abundance(path)

        assert len(entries) == 2
        assert entries[0].taxon_id == 853
        assert entries[0].name == "Faecalibacterium prausnitzii"
        assert entries[0].rank == "species"
        assert entries[0].abundance == pytest.approx(0.2)
        assert entries[0].superkingdom == "Bacteria"

        assert entries[1].taxon_id == 562
        assert entries[1].name == "Escherichia coli"

    def test_filters_unmapped_and_mapped_unclassified(self, tmp_path):
        path = write_tsv(tmp_path, MINIMAL_TSV)
        entries = read_emu_abundance(path)

        tax_ids = {e.taxon_id for e in entries}
        assert "unmapped" not in tax_ids
        assert "mapped_unclassified" not in tax_ids
        assert len(entries) == 2

    def test_filters_zero_abundance(self, tmp_path):
        path = write_tsv(tmp_path, ZERO_ABUNDANCE_TSV)
        entries = read_emu_abundance(path)

        assert len(entries) == 0

    def test_fallback_to_genus_when_no_species(self, tmp_path):
        path = write_tsv(tmp_path, NO_SPECIES_TSV)
        entries = read_emu_abundance(path)

        assert len(entries) == 1
        assert entries[0].name == "Staphylococcus"
        assert entries[0].rank == "genus"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Emu abundance file not found"):
            read_emu_abundance(str(tmp_path / "nonexistent.tsv"))

    def test_missing_required_columns(self, tmp_path):
        content = "name\tgenus\n853\tFaecalibacterium\n"
        path = write_tsv(tmp_path, content)
        with pytest.raises(ValueError, match="missing required columns"):
            read_emu_abundance(path)

