from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class RunDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    run_id: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    sample_ids: list[str] = []

    model_config = {"populate_by_name": True}


class RunCreate(BaseModel):
    run_id: str