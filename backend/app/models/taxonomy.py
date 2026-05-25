# app/models/taxonomy.py
"""Taxonomic profile entries — one TaxonEntry per row of a taxpasta profile,
grouped under a ClassifierProfile in sample documents."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class _StrictBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxonEntry(_StrictBase):
    """One row from a TAXPASTA profile after normalisation."""

    taxon_id: int
    name: str
    rank: Optional[str] = None
    abundance: float
    superkingdom: Optional[str] = None  # Bacteria | Archaea | Eukaryota | Viruses


class ClassifierProfile(BaseModel):
    classifier: str
    classifier_db: str
    profile: List[TaxonEntry]
