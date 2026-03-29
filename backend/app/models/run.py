from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class CaseDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    run_id: str                               # MongoDB field name kept as run_id (storage key)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    sample_ids: list[str] = []

    model_config = {"populate_by_name": True}


class CaseCreate(BaseModel):
    run_id: str