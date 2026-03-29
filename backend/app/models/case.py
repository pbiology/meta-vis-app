# app/models/case.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class CaseDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    case_id: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    sample_ids: list[str] = []

    model_config = {"populate_by_name": True}


class CaseCreate(BaseModel):
    case_id: str
