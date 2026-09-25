# app/models/ingest.py
"""Ingest manifest models — the wire contract between the ingest CLI and the
backend. The CLI uploads a tar.gz bundle whose manifest.json deserialises into
one of the *IngestMeta models below. File paths are NOT part of the wire
model — everything is addressed by arcname inside the bundle
(see app.ingestor.loader)."""

from collections.abc import Sequence
from datetime import date
from typing import List, Literal, Optional, Protocol

from pydantic import BaseModel, Field, model_validator

from app.models.common import AnalysisType, SequencingPlatform


# ---------------------------------------------------------------------------
# Shared sample-entry rules
# ---------------------------------------------------------------------------


def _assert_order_date_is_control_only(
    sample_id: str, sample_type: str, order_date: Optional[date]
) -> None:
    """Reject a per-sample order date on a clinical sample.

    A control is prepared once and sequenced alongside every case in its run, so
    its order date belongs to the control. A clinical sample is ordered as part
    of its case, so a date of its own could only disagree with the case's — the
    drift this field exists to remove, not to introduce.
    """
    if sample_type == "sample" and order_date is not None:
        raise ValueError(
            f"Sample '{sample_id}' has sample_type='sample' and must not set "
            "order_date: a clinical sample is ordered as part of its case and "
            "takes the case's order date. Only controls carry their own."
        )


def _assert_negative_controls_declared(
    sample_id: str, sample_type: str, negative_controls: Optional[List[str]]
) -> None:
    """Require a declared control list on everything but a negative control.

    Which negative control belongs to which sample is never inferred: a run can
    hold several controls per nucleic acid (one per prep method, say), and
    comparing a sample with another prep's control flags the wrong
    contaminants. An empty list is the explicit "this sample has no control",
    which the UI surfaces as a warning, so omitting the field is never read as
    that. A negative control has no control of its own.
    """
    if sample_type == "negative_ctrl":
        if negative_controls is not None:
            raise ValueError(
                f"Sample '{sample_id}' is a negative_ctrl and must not declare "
                "negative_controls."
            )
        return
    if negative_controls is None:
        raise ValueError(
            f"Sample '{sample_id}' has sample_type='{sample_type}' and must "
            "declare negative_controls (an empty list when it has none)."
        )
    duplicates = sorted(
        {c for c in negative_controls if negative_controls.count(c) > 1}
    )
    if duplicates:
        raise ValueError(
            f"Sample '{sample_id}' lists negative control(s) more than once: "
            f"{duplicates}"
        )


class _SampleEntry(Protocol):
    """The fields the bundle-wide checks read, shared by both pipelines."""

    @property
    def sample_id(self) -> str: ...
    @property
    def sample_type(self) -> str: ...
    @property
    def nucleic_acid(self) -> str: ...
    @property
    def negative_controls(self) -> Optional[List[str]]: ...


def _assert_control_references(samples: Sequence[_SampleEntry]) -> None:
    """Check that every declared negative control resolves within the bundle.

    Samples reference their controls by sample_id, so sample_ids must be unique
    in the bundle for a reference to mean one thing. Each reference must name a
    negative control of the same nucleic acid: DNA and RNA controls are not
    comparable, and pointing at a clinical sample is always an operator error.
    """
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for s in samples:
        (duplicate_ids if s.sample_id in seen else seen).add(s.sample_id)
    if duplicate_ids:
        raise ValueError(
            f"sample_id must be unique within a bundle; repeated: "
            f"{sorted(duplicate_ids)}"
        )

    by_id = {s.sample_id: s for s in samples}
    for s in samples:
        for ref in s.negative_controls or []:
            control = by_id.get(ref)
            if control is None:
                raise ValueError(
                    f"Sample '{s.sample_id}' declares negative control '{ref}', "
                    "which is not a sample in this bundle."
                )
            if control.sample_type != "negative_ctrl":
                raise ValueError(
                    f"Sample '{s.sample_id}' declares '{ref}' as a negative "
                    f"control, but it has sample_type='{control.sample_type}'."
                )
            if control.nucleic_acid != s.nucleic_acid:
                raise ValueError(
                    f"Sample '{s.sample_id}' ({s.nucleic_acid}) declares "
                    f"negative control '{ref}' ({control.nucleic_acid}); a "
                    "control must match the sample's nucleic acid."
                )


# ---------------------------------------------------------------------------
# Taxprofiler ingest manifest
# ---------------------------------------------------------------------------


class TaxprofilerClassifierMeta(BaseModel):
    """One classifier within a taxprofiler ingest manifest."""

    name: str  # e.g. "kraken2" or "centrifuge"
    db: str  # e.g. "k2_pluspf" or "p_compressed+h+v"


class TaxprofilerSampleIngestRequest(BaseModel):
    # subject_id is required for clinical samples but not for controls (NTC /
    # positive control) — controls have no clinical subject. The validator
    # below enforces this. subject_sex is only persisted when a subject_id is
    # present.
    subject_id: Optional[str] = None
    subject_sex: Literal["F", "M", "X", "unknown"] = "unknown"
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    nucleic_acid: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    # A control is prepared once and sequenced alongside every case in its run,
    # so its order date is a property of the control, not of any one case. Left
    # unset, the sample inherits the case's order date — always right for a
    # clinical sample, which is why the validator below rejects it there.
    order_date: Optional[date] = None
    # sample_ids of the negative controls in this bundle that this sample is
    # compared against. Required on everything but a negative control; an empty
    # list declares "no control". See _assert_negative_controls_declared.
    negative_controls: Optional[List[str]] = None
    # classifier_name -> taxpasta column name
    columns: dict

    @model_validator(mode="after")
    def _require_subject_for_clinical_samples(self):
        if self.sample_type == "sample" and not self.subject_id:
            raise ValueError(
                f"Sample '{self.sample_id}' has sample_type='sample' and must "
                "provide a subject_id."
            )
        return self

    @model_validator(mode="after")
    def _reject_order_date_on_clinical_samples(self):
        _assert_order_date_is_control_only(
            self.sample_id, self.sample_type, self.order_date
        )
        return self

    @model_validator(mode="after")
    def _require_negative_controls(self):
        _assert_negative_controls_declared(
            self.sample_id, self.sample_type, self.negative_controls
        )
        return self


class TaxprofilerIngestMeta(BaseModel):
    """Taxprofiler ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    classifiers: List[TaxprofilerClassifierMeta]
    samples: List[TaxprofilerSampleIngestRequest]
    # True iff the bundle includes a metaval/ subtree.
    has_metaval: bool = False
    # True iff classifiers/<name>/krona/<file> is present for the named classifier.
    classifiers_with_krona: List[str] = Field(default_factory=list)
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None

    @model_validator(mode="after")
    def _check_control_references(self):
        _assert_control_references(self.samples)
        return self


# ---------------------------------------------------------------------------
# Trana ingest manifest
# ---------------------------------------------------------------------------


class TranaSampleIngestRequest(BaseModel):
    """Per-sample input for Trana pipeline ingest. Files live in the bundle
    under samples/<sample_id>/ (abundance.tsv, optional krona.html,
    optional nanoplot_unprocessed/NanoStats.txt, optional
    nanoplot_processed/NanoStats.txt)."""

    # See TaxprofilerSampleIngestRequest for the subject_id / sample_type,
    # order_date and negative_controls rules.
    subject_id: Optional[str] = None
    subject_sex: Literal["F", "M", "X", "unknown"] = "unknown"
    sample_id: str
    sample_type: Literal["sample", "positive_ctrl", "negative_ctrl"]
    nucleic_acid: Literal["DNA", "RNA"]
    sample_source: str = "N/A"
    order_date: Optional[date] = None
    negative_controls: Optional[List[str]] = None
    has_krona: bool = False
    has_nanoplot_unprocessed: bool = False
    has_nanoplot_processed: bool = False

    @model_validator(mode="after")
    def _require_subject_for_clinical_samples(self):
        if self.sample_type == "sample" and not self.subject_id:
            raise ValueError(
                f"Sample '{self.sample_id}' has sample_type='sample' and must "
                "provide a subject_id."
            )
        return self

    @model_validator(mode="after")
    def _reject_order_date_on_clinical_samples(self):
        _assert_order_date_is_control_only(
            self.sample_id, self.sample_type, self.order_date
        )
        return self

    @model_validator(mode="after")
    def _require_negative_controls(self):
        _assert_negative_controls_declared(
            self.sample_id, self.sample_type, self.negative_controls
        )
        return self


class TranaIngestMeta(BaseModel):
    """Trana ingest manifest. Carried as manifest.json inside the bundle."""

    case_id: str
    ticket_id: Optional[str] = None
    order_date: Optional[date] = None
    samples: List[TranaSampleIngestRequest]
    has_multiqc_report: bool = False
    analysis_type: Optional[AnalysisType] = None
    sequencing_platform: Optional[SequencingPlatform] = None

    @model_validator(mode="after")
    def _check_control_references(self):
        _assert_control_references(self.samples)
        return self
