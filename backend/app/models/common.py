# app/models/common.py
"""Shared base class, enums, and small subdocuments used across model files."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnalysisType(str, Enum):
    SHOTGUN = "shotgun"
    AMPLICON = "amplicon"


class SequencingPlatform(str, Enum):
    ILLUMINA = "illumina"
    NANOPORE = "nanopore"


class _Base(BaseModel):
    """Permissive base for response models read out of MongoDB.

    `extra="ignore"` lets the API tolerate documents that pre-date current
    fields without bumping every model on every schema addition.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ReviewStatus(_Base):
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None
