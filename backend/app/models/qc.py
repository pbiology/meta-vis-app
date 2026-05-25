# app/models/qc.py
"""QC stat blocks attached to sample documents.

Two pipeline-shaped wrappers live here:
- TaxprofilerStats   (fastp, fastqc, bowtie2, per-classifier QC, pipeline_info)
- TranaStats         (nanoplot before/after, pipeline_info)
"""

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.models.common import _Base
from app.models.pipeline import PipelineInfo


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FastQCStats(_Base):
    total_sequences: Optional[int] = None
    avg_sequence_length: Optional[float] = None
    pct_gc_forward: Optional[float] = None
    pct_gc_reverse: Optional[float] = None
    pct_poor_quality_forward: Optional[float] = None
    pct_poor_quality_reverse: Optional[float] = None


class FastpStats(_Base):
    total_reads_before_filtering: Optional[int] = None
    total_reads_after_filtering: Optional[int] = None
    passed_filter_reads: Optional[int] = None
    low_quality_reads: Optional[int] = None
    too_short_reads: Optional[int] = None
    q20_rate: Optional[float] = None
    q30_rate: Optional[float] = None
    gc_content: Optional[float] = None


class ClassifierQcStats(_Base):
    pct_unclassified: Optional[float] = None
    unclassified_reads: Optional[int] = None
    classified_reads: Optional[int] = None
    total_reads: Optional[int] = None
    num_species: Optional[int] = None
    num_genera: Optional[int] = None
    queries_aligned: Optional[int] = None  # diamond only


class Bowtie2Stats(_Base):
    total_reads: Optional[int] = None
    aligned_exactly_one: Optional[int] = None
    aligned_multi: Optional[int] = None
    aligned_none: Optional[int] = None
    overall_alignment_rate: Optional[float] = None


class TaxprofilerStats(_Base):
    fastp: Optional[FastpStats] = None
    fastqc: Optional[FastQCStats] = None
    bowtie2: Optional[Bowtie2Stats] = None
    classifiers: Optional[Dict[str, ClassifierQcStats]] = None
    pipeline_info: Optional[PipelineInfo] = None


class NanoPlotStats(_StrictBase):
    """QC metrics parsed from a NanoPlot NanoStats.txt file (ingest-side, strict)."""

    mean_read_length: Optional[float] = None
    mean_read_quality: Optional[float] = None
    median_read_length: Optional[float] = None
    median_read_quality: Optional[float] = None
    number_of_reads: Optional[int] = None
    read_length_n50: Optional[int] = None
    total_bases: Optional[int] = None


class NanoPlotStatsResponse(_Base):
    """NanoPlot QC metrics returned by the API (permissive)."""

    mean_read_length: Optional[float] = None
    mean_read_quality: Optional[float] = None
    median_read_length: Optional[float] = None
    median_read_quality: Optional[float] = None
    number_of_reads: Optional[int] = None
    read_length_n50: Optional[int] = None
    total_bases: Optional[int] = None


class TranaStats(_Base):
    """QC block for Trana pipeline samples (parallel to TaxprofilerStats)."""

    nanoplot_unprocessed: Optional[NanoPlotStatsResponse] = None
    nanoplot_processed: Optional[NanoPlotStatsResponse] = None
    pipeline_info: Optional[PipelineInfo] = None
