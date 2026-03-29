# app/models/case.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class CaseDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    run_id: str                               # case identifier string (kept as run_id for ingest CLI compat)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    sample_ids: list[str] = []

    model_config = {"populate_by_name": True}


class CaseCreate(BaseModel):
    run_id: str
