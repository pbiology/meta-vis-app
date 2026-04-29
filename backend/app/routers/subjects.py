# app/routers/subjects.py

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth.utils import get_current_user
from app.database import get_db
from app.models.subject import Subject

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/{subject_id}", response_model=Subject, summary="Get a subject by id")
async def get_subject(
    subject_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> Subject:
    # Exclude _id so the ObjectId doesn't leak through extra="allow".
    doc = await db["subjects"].find_one({"subject_id": subject_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")
    return Subject.model_validate(doc)
