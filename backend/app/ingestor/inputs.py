# app/ingestor/inputs.py
"""Ingest-internal types: raw parser shapes and the dataclass containers
the loader hands to the orchestrator.

Persisted/API-facing models live under ``app.models``; this module is
deliberately limited to types whose only purpose is to flow between
loader and orchestrator (plus the strict MultiQC parse shape)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.metaval import MetavalOutput
from app.models.pipeline import PipelineInfo
from app.models.qc import NanoPlotStats
from app.models.taxonomy import TaxonEntry

if TYPE_CHECKING:
    import pandas as pd


class _StrictBase(BaseModel):
    """Base with strict validation: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


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
# Ingest inputs — fully-parsed content handed from the loader to the
# orchestrator. The orchestrator never touches user-supplied paths; whatever
# filesystem reads still happen (IGV HTMLs, verification-data FASTAs) read
# only files that the loader itself extracted into a TemporaryDirectory.
# ---------------------------------------------------------------------------


@dataclass
class TaxprofilerIngestInputs:
    """Parsed inputs for a taxprofiler ingest. All file I/O has already
    happened in the loader (with the exception of metaval IGV/verification-data
    blobs, which are streamed lazily from the loader's temp dir during the
    prepare phase — see orchestrator._prepare_metaval_result)."""

    multiqc: MultiQCRaw
    pipeline_info: PipelineInfo
    # classifier name -> taxpasta DataFrame
    taxpasta: dict[str, "pd.DataFrame"] = field(default_factory=dict)
    # classifier name -> krona HTML content (only classifiers that had a krona)
    krona_html: dict[str, str] = field(default_factory=dict)
    multiqc_html: Optional[str] = None
    metaval: Optional[MetavalOutput] = None


@dataclass
class TranaSampleInputs:
    """Per-sample parsed inputs for a Trana ingest."""

    taxon_entries: list[TaxonEntry]
    nanoplot_unprocessed: Optional[NanoPlotStats] = None
    nanoplot_processed: Optional[NanoPlotStats] = None
    krona_html: Optional[str] = None


@dataclass
class TranaIngestInputs:
    """Parsed inputs for a Trana ingest."""

    pipeline_info: PipelineInfo
    # sample_id -> parsed per-sample content
    samples: dict[str, TranaSampleInputs] = field(default_factory=dict)
    multiqc_html: Optional[str] = None
