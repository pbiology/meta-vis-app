# app/ingestor/models.py

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class _StrictBase(BaseModel):
    """Base with strict validation: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared / re-exported
# ---------------------------------------------------------------------------


class TaxonEntry(_StrictBase):
    """One row from a TAXPASTA profile after normalisation."""

    taxon_id: int
    name: str
    rank: Optional[str] = None
    abundance: float
    superkingdom: Optional[str] = None  # Bacteria | Archaea | Eukaryota | Viruses


# ---------------------------------------------------------------------------
# Pipeline info
# ---------------------------------------------------------------------------


class PipelineConfiguration(_StrictBase):
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[str] = None
    nextflow: Optional[str] = None


class PipelineInfoOutput(_StrictBase):
    """Validated output of pipeline_info_reader.read_pipeline_info()."""

    software_used: dict[str, Any]
    pipeline_configuration: PipelineConfiguration


# ---------------------------------------------------------------------------
# MultiQC raw data
# ---------------------------------------------------------------------------


class MultiQCRaw(_StrictBase):
    """Validated output of multiqc_reader.read_multiqc().

    kraken2 / centrifuge use the MultiQC v2 dict-of-dicts format:
      sample_name -> rank_code -> {taxon_name: count}
    e.g. {"SAMPLE1_k2_pluspf": {"U": {"unclassified": 200}, "S": {"Homo sapiens": 1000}}}

    diamond uses a flat format:
      sample_name -> {stat_name: int}
    e.g. {"SAMPLE1_diamond": {"queries_aligned": 723522}}

    Pydantic will reject unexpected formats at parse time.
    fastqc / fastp / bowtie2 inner structures vary enough to stay as Any.
    """

    kraken2: dict[str, dict[str, dict[str, int]]]
    centrifuge: dict[str, dict[str, dict[str, int]]]
    diamond: dict[str, dict[str, int]]
    fastqc: dict[str, Any]
    fastp: dict[str, Any]
    bowtie2: dict[str, Any]


# ---------------------------------------------------------------------------
# NanoPlot QC (Trana pipeline)
# ---------------------------------------------------------------------------


class NanoPlotStats(_StrictBase):
    """QC metrics parsed from a NanoPlot NanoStats.txt file."""

    mean_read_length: Optional[float] = None
    mean_read_quality: Optional[float] = None
    median_read_length: Optional[float] = None
    median_read_quality: Optional[float] = None
    number_of_reads: Optional[int] = None
    read_length_n50: Optional[int] = None
    total_bases: Optional[int] = None


# ---------------------------------------------------------------------------
# Metaval output models
# ---------------------------------------------------------------------------


class IgvOrganism(_StrictBase):
    """One organism entry under a metaval IGV group."""

    organism_name: str
    igv_file_path: str
    igv_file_size_bytes: int
    igv_too_large: bool


class BlastHits(_StrictBase):
    """BLAST results for a single (sample, classifier, taxon) group.

    Rows are kept as list[dict[str, str]] because blastn/blastx column
    sets vary across pipeline versions and modes.
    """

    blastn: list[dict[str, str]]
    blastx: list[dict[str, str]]


class VerificationData(_StrictBase):
    """Sequence evidence attached to a metaval result.

    ``type`` is one of: ``"scaffolds"``, ``"contigs"``, ``"raw_reads"``.
    Path fields are optional because not all types have all paths.
    """

    type: str
    count: int
    avg_length: float
    # scaffolds / contigs
    path: Optional[str] = None
    # raw_reads
    read_1_path: Optional[str] = None
    read_2_path: Optional[str] = None
    file_count: Optional[int] = None


class MetavalResult(_StrictBase):
    """One (sample, classifier, taxon) group from the metaval output."""

    sample_name: str
    classifier: str
    taxon_id: Optional[int] = None
    taxon_name: str
    organisms: list[IgvOrganism]
    blast: BlastHits
    verification_data: VerificationData


class MetavalOutput(_StrictBase):
    """Validated output of metaval_reader.read_metaval()."""

    results: list[MetavalResult]
    pipeline_info: Optional[PipelineInfoOutput] = None
