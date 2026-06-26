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
    material: Optional[str] = None
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


class SampleResponse(_Base):
    """Validated response model for sample documents read from MongoDB."""

    case_id: str
    sample_id: str
    sample_source: Optional[str] = None
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    material: Literal["DNA", "RNA"]
    subject_id: Optional[str] = None
    taxprofiler: Optional[TaxprofilerStats] = None
    trana: Optional[TranaStats] = None
    profiles: List[ClassifierProfile] = []
    has_krona: bool = False
    # Derived at read time from the parent case: true when a metaval analysis
    # was ingested for the case. Lets the UI distinguish "no metaval run" from
    # "metaval run but no taxa found". Metaval is case-level, so this is the
    # same for every sample in a case.
    has_metaval: bool = False
    review: ReviewStatus = ReviewStatus()
    ingested_at: Optional[datetime] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)
