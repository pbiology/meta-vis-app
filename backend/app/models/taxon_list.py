# app/models/taxon_list.py
"""Curated taxon lists (``taxon_lists``) and their entries (``taxon_list_entries``)."""

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common import _Base
from app.taxon_lists.kinds import TaxonListKind


class TaxonList(_Base):
    """One curated list: what it is for, and who made it."""

    list_id: str
    kind: TaxonListKind
    name: str
    description: Optional[str] = None
    # Seeded at startup and referenced by the analytics; never user-deleted.
    system: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaxonListSummary(TaxonList):
    """A list as shown in overviews, with how many taxa it holds."""

    entry_count: int


class TaxonListEntry(_Base):
    """One taxon on one list. A taxon on several lists has one entry per list."""

    list_id: str
    taxon_id: int
    # Resolved from `taxa` when the entry is added, never taken from the client.
    taxon_name: str
    superkingdom: Optional[str] = None
    reason: Optional[str] = None
    # Kind-specific: only lists whose kind declares it (see KIND_SPECS).
    min_reads: Optional[int] = None
    added_by: str
    added_at: datetime
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class TaxonListEntryOut(TaxonListEntry):
    """An entry as the API returns it.

    ``merged_ids`` are the retired NCBI ids merged into this taxon, which the
    list also matches. Derived from ``taxa_retired`` on every read, never
    stored: a taxonomy reload can change them.
    """

    merged_ids: list[int] = []


class ContaminantEntry(TaxonListEntry):
    """An NTC known-contaminant entry, whose threshold must be present."""

    min_reads: int


class TaxonListCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Only user-creatable kinds are accepted; the service enforces it.
    kind: TaxonListKind
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class TaxonListUpdate(BaseModel):
    """Partial update; a present ``"description": null`` clears it."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _valid(self) -> "TaxonListUpdate":
        if not self.model_fields_set:
            raise ValueError("No fields to update")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class _EntryInput(BaseModel):
    # Unknown keys fail loudly: a client still sending the old `taxon_name` /
    # `superkingdom` / `notes` fields gets a 422 rather than silently losing them.
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=2000)
    min_reads: Optional[int] = Field(default=None, ge=0)

    def kind_specific_fields(self) -> dict[str, object]:
        """The kind-specific fields the client actually set, validated by
        the service against the list's kind."""
        return {
            name: getattr(self, name)
            for name in ("min_reads",)
            if name in self.model_fields_set
        }


class TaxonListEntryCreate(_EntryInput):
    taxon_id: int = Field(ge=1)


class TaxonListEntryUpdate(_EntryInput):
    """Partial update. Only fields present in the body are changed, so sending
    ``"reason": null`` clears the reason while omitting it leaves it alone."""

    @model_validator(mode="after")
    def _not_empty(self) -> "TaxonListEntryUpdate":
        if not self.model_fields_set:
            raise ValueError("No fields to update")
        return self


# Sized for real curated lists (tens of thousands of taxa). At this size the
# insert is ~19 MB in one transaction (fine on MongoDB >= 4.2), the request
# body ~600 KB and the audit event under 2 MB — all well inside their limits.
MAX_BULK_TAXA = 75_000

# The preview names only this many of the taxa it would add; the rest are
# counted. Skipped and rejected ids are always listed in full.
BULK_SAMPLE_SIZE = 100


class TaxonListBulkAdd(_EntryInput):
    """Add many taxa at once. ``reason``/``min_reads`` apply to every entry.

    ``dry_run`` returns the report without writing, for a preview the user
    confirms before anything is added.
    """

    taxon_ids: list[Annotated[int, Field(ge=1)]] = Field(
        min_length=1, max_length=MAX_BULK_TAXA
    )
    dry_run: bool = False


class TaxonToAdd(BaseModel):
    taxon_id: int
    taxon_name: str
    superkingdom: Optional[str] = None


class RejectedTaxon(BaseModel):
    """Compact on purpose: a large paste can reject tens of thousands of ids."""

    taxon_id: int
    reason: Literal["not_in_taxonomy", "merged", "deleted", "excluded_by_list"]
    merged_into: Optional[int] = None


class ReplacedTaxon(BaseModel):
    """A requested id NCBI merged into another; the current id was used."""

    taxon_id: int
    merged_into: int


class BulkAddReport(BaseModel):
    """Where every requested id went. Each id is in exactly one group:

    to add (counted, first ``BULK_SAMPLE_SIZE`` named), already on the list,
    or rejected. The ids to add are the requested ids minus the other two.
    """

    to_add_count: int
    to_add_sample: list[TaxonToAdd]
    already_on_list: list[int]
    rejected: list[RejectedTaxon]
    # Merged ids replaced by their current id. Informational: each is also
    # counted in to_add or already_on_list, by what happened to the current id.
    replaced: list[ReplacedTaxon]
    # How many entries were written: 0 for a dry run.
    added: int


class TaxonListEntryPage(BaseModel):
    items: list[TaxonListEntryOut]
    total: int
    offset: int
    limit: int


class TaxonListTaxonIds(BaseModel):
    """Every id the list matches, uncapped: its taxa plus the retired ids
    merged into them — what the display filter needs."""

    list_id: str
    count: int
    taxon_ids: list[int]
