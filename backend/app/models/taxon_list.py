# app/models/taxon_list.py
"""Curated taxon lists (``taxon_lists``) and their entries (``taxon_list_entries``)."""

from datetime import datetime
from typing import Optional

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


class ContaminantEntry(TaxonListEntry):
    """An NTC known-contaminant entry, whose threshold must be present."""

    min_reads: int


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
