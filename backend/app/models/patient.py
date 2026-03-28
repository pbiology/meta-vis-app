from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PatientDocument(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    patient_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class PatientCreate(BaseModel):
    patient_id: str