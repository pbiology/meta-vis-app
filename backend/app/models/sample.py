# app/models/sample.py
"""Sample response model — one document per sequenced sample, stored in the
``samples`` collection."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import ConfigDict

from app.models.common import ReviewStatus, _Base
from app.models.qc import TaxprofilerStats, TranaStats
from app.models.taxonomy import ClassifierProfile


class SampleMetadata(_Base):
    sample_id: str
    sample_source: Optional[str] = None
    nucleic_acid: Optional[str] = None
    sample_type: Optional[str] = None
    subject_id: Optional[str] = None
    biopsy_id: Optional[str] = None


class LibraryPreparation(_Base):
    library_name: Optional[str] = None
    batch_id: Optional[str] = None
    sample_type: Optional[str] = None


class SequencingMetadata(_Base):
    platform: Optional[str] = None
    flowcell_id: Optional[str] = None
    date: Optional[str] = None
    barcode_index: Optional[str] = None
    num_reads: Optional[int] = None


# "unknown" exists so a missing read count on either side cannot be mistaken
# for "unchanged" — the two are very different clinically.
ReadDeltaStatus = Literal["new", "increased", "unchanged", "decreased", "unknown"]


class SampleReadDelta(_Base):
    """How a sample's raw input read count compares to an earlier analysis.

    A case is delivered twice on purpose: a deliberately partial dataset first
    so analysis can start sooner, then a top-up for any sample short of the
    agreed data amount. This block is what lets the UI tell a topped-up sample
    from one re-delivered unchanged — the latter being the clinically
    interesting case, since it is still below depth.

    Computed at read time by ``app.sample_read_deltas``; never stored.
    """

    status: ReadDeltaStatus
    current_reads: Optional[int] = None
    previous_reads: Optional[int] = None
    # Version of the most recent earlier analysis containing this sample.
    # None when the sample is new.
    previous_version: Optional[int] = None
    delta_reads: Optional[int] = None
    pct_change: Optional[float] = None


class SampleResponse(_Base):
    """Validated response model for sample documents read from MongoDB."""

    # ObjectId of the case_analysis that produced this sample, serialised as
    # str. This is the foreign key; `case_id` is denormalised alongside it so
    # cross-case aggregations can group by clinical case without a join.
    analysis_id: Optional[str] = None
    case_id: str
    # True when this sample belongs to its case's latest analysis. Denormalised
    # so analytics filter on an indexed equality rather than excluding the
    # superseded analyses by id.
    is_latest_analysis: bool = True
    sample_id: str
    sample_source: Optional[str] = None
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    nucleic_acid: Literal["DNA", "RNA"]
    subject_id: Optional[str] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    trana: Optional[TranaStats] = None
    profiles: List[ClassifierProfile] = []
    has_krona: bool = False
    # Raw input reads, resolved server-side by app.sample_read_deltas.read_count
    # so the displayed count and the comparison behind read_delta come from one
    # definition. Deriving it again client-side let the two disagree on a
    # document carrying blocks from both pipelines.
    total_reads: Optional[int] = None
    # True when at least one classifier profile carries entries. Lets the UI
    # tell a control that produced no classifier data from one that was never
    # part of the run — an empty NTC silently disables contaminant flagging.
    has_profile_data: bool = False
    # Absent on a case's first analysis: with nothing to compare against, every
    # sample would otherwise be labelled as if it had failed to gain data.
    read_delta: Optional[SampleReadDelta] = None
    # Derived at read time from the parent case: true when a metaval analysis
    # was ingested for the case. Lets the UI distinguish "no metaval run" from
    # "metaval run but no taxa found". Metaval is case-level, so this is the
    # same for every sample in a case.
    has_metaval: bool = False
    review: ReviewStatus = ReviewStatus()
    ingested_at: Optional[datetime] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)
