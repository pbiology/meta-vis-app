# app/models/metaval.py
"""Metaval (BLAST + IGV verification) result models.

Read out of the ``metaval_results`` collection and served by routers/metaval.py.
Also produced by the metaval reader during ingest.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict

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
