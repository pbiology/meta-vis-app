# app/models/metaval.py
"""Metaval (BLAST + IGV verification) result models.

Read out of the ``metaval_results`` collection and served by routers/metaval.py.
Also produced by the metaval reader during ingest.
"""

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.common import _Base
from app.models.pipeline import PipelineInfo


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    pipeline_info: Optional[PipelineInfo] = None


# ---------------------------------------------------------------------------
# Response models — the stored ``metaval_results`` document as the API serves
# it. Separate from the ingest models above: the stored shape carries blob keys
# instead of file paths, and those keys never leave the backend.
# ---------------------------------------------------------------------------

_TAXID_PREFIX = re.compile(r"^taxid_\d+_")


def display_taxon_name(taxon_name: str) -> str:
    """Human-readable taxon name from a metaval file-derived name.

    New-format metaval filenames embed ``taxid_<id>_`` and use dashes for
    spaces (``taxid_10239_Human-mastadenovirus-C``).
    """
    return _TAXID_PREFIX.sub("", taxon_name).replace("-", " ")


class _MetavalResponseBase(_Base):
    id: str = Field(alias="_id")
    classifier: str
    # None for old-format metaval output whose taxon could not be resolved.
    # Such a result has no row in the taxonomy table; the UI lists it apart.
    taxon_id: Optional[int] = None
    taxon_name: str

    # mypy rejects any decorator stacked on @property; pydantic's documented
    # computed_field usage needs this ignore.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_name(self) -> str:
        return display_taxon_name(self.taxon_name)


class MetavalSummary(_MetavalResponseBase):
    """GET /metaval/sample/{id} — enough to place each result in the
    taxonomy table and link to its details. BLAST rows stay on the detail
    endpoint: they are the bulk of the document."""

    sample_id: str


class MetavalOrganismResponse(_Base):
    organism_name: str
    igv_file_size_bytes: int
    igv_too_large: bool


class VerificationDataResponse(_Base):
    type: Literal["scaffolds", "contigs", "raw_reads"]
    count: int
    avg_length: float
    file_count: Optional[int] = None
    # Whether the sequences were stored at ingest and can be sent to BLAST.
    available: bool


class MetavalDetailResponse(_MetavalResponseBase):
    """GET /metaval/{id} — the full result, minus internal blob keys."""

    # None when ingest could not map the metaval sample name to a sample.
    sample_id: Optional[str] = None
    sample_name: str
    organisms: list[MetavalOrganismResponse]
    blast: BlastHits
    verification_data: VerificationDataResponse
