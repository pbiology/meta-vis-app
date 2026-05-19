# app/routers/users.py
#
# User identity is owned by Keycloak. The Mongo `users` collection only
# stores per-user app preferences and is keyed by the OIDC `sub` claim
# (stable across username/email changes).

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

REVIEWER_TITLES = [
    (0, "Newbie"),
    (1, "Initiate"),
    (5, "Novice"),
    (15, "Apprentice"),
    (30, "Disciple"),
    (60, "Adept"),
    (100, "Journeyman"),
    (175, "Veteran"),
    (250, "Expert"),
    (300, "Master"),
    (500, "Grand Master"),
]


def reviewer_title(count: int) -> str:
    title = REVIEWER_TITLES[0][1]
    for threshold, t in REVIEWER_TITLES:
        if count >= threshold:
            title = t
    return title


VALID_KINGDOMS: frozenset[str] = frozenset(
    {"Bacteria", "Viruses", "Eukaryota", "Archaea"}
)

VALID_ANALYSIS_TYPES: frozenset[str] = frozenset({"shotgun", "amplicon"})


class UserPreferences(BaseModel):
    preferred_kingdoms: list[str] = ["Viruses"]
    visible_analysis_types: list[str] = ["shotgun", "amplicon"]

    @field_validator("preferred_kingdoms")
    @classmethod
    def kingdoms_must_be_valid(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_KINGDOMS
        if invalid:
            raise ValueError(f"Invalid kingdoms: {invalid}")
        return v

    @field_validator("visible_analysis_types")
    @classmethod
    def analysis_types_must_be_valid(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_ANALYSIS_TYPES
        if invalid:
            raise ValueError(f"Invalid analysis types: {invalid}")
        if not v:
            raise ValueError("At least one analysis type must be visible")
        return v


async def _count_reviews(db: AsyncIOMotorDatabase, username: str) -> int:
    return await db["cases"].count_documents(
        {"review.reviewed_by": username, "review.reviewed": True}
    )


@router.get("/me/stats", summary="Get review stats for the current user")
async def get_my_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    count = await _count_reviews(db, current_user["username"])
    return {
        "username": current_user["username"],
        "reviews": count,
        "reviewer_title": reviewer_title(count),
    }


@router.get("/me/preferences", summary="Get current user's preferences")
async def get_my_preferences(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> UserPreferences:
    doc = await db["users"].find_one({"sub": current_user["sub"]}, {"preferences": 1})
    prefs: dict = (doc or {}).get("preferences") or {}
    return UserPreferences(**prefs)


@router.patch("/me/preferences", summary="Update current user's preferences")
async def update_my_preferences(
    body: UserPreferences,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> UserPreferences:
    await db["users"].update_one(
        {"sub": current_user["sub"]},
        {
            "$set": {
                "preferences": body.model_dump(),
                "username": current_user["username"],
            }
        },
        upsert=True,
    )
    return body
