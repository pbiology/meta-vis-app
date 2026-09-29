# app/routers/users.py
#
# User identity is owned by Keycloak. The Mongo `users` collection only
# stores per-user app preferences and is keyed by the OIDC `sub` claim
# (stable across username/email changes).

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pymongo import ReturnDocument

from app.database import get_db
from app.auth.utils import get_current_user
from app.taxon_lists import store as taxon_lists
from app.taxon_lists.kinds import TaxonListKind

logger = logging.getLogger(__name__)

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


# Both checks pass None through: in UserPreferencesUpdate a null is rejected by
# its model validator, which runs after these.
def _check_kingdoms(v: Optional[list[str]]) -> Optional[list[str]]:
    if v is None:
        return v
    invalid = set(v) - VALID_KINGDOMS
    if invalid:
        raise ValueError(f"Invalid kingdoms: {invalid}")
    return v


def _check_analysis_types(v: Optional[list[str]]) -> Optional[list[str]]:
    if v is None:
        return v
    invalid = set(v) - VALID_ANALYSIS_TYPES
    if invalid:
        raise ValueError(f"Invalid analysis types: {invalid}")
    if not v:
        raise ValueError("At least one analysis type must be visible")
    return v


class UserPreferences(BaseModel):
    preferred_kingdoms: list[str] = ["Viruses"]
    visible_analysis_types: list[str] = ["shotgun", "amplicon"]
    # list_ids of the display-filter taxon lists hiding taxa from this user's
    # taxonomy table. Existence is checked against the DB in the PATCH handler.
    active_display_filters: list[str] = []

    _kingdoms = field_validator("preferred_kingdoms")(_check_kingdoms)
    _analysis_types = field_validator("visible_analysis_types")(_check_analysis_types)


class UserPreferencesUpdate(BaseModel):
    """Partial update: only the fields sent are changed.

    PATCH used to replace the stored preferences with a full model, so a
    client sending one field silently reset the others to their defaults.
    """

    model_config = ConfigDict(extra="forbid")

    preferred_kingdoms: Optional[list[str]] = None
    visible_analysis_types: Optional[list[str]] = None
    active_display_filters: Optional[list[str]] = None

    _kingdoms = field_validator("preferred_kingdoms")(_check_kingdoms)
    _analysis_types = field_validator("visible_analysis_types")(_check_analysis_types)

    @model_validator(mode="after")
    def _no_nulls(self) -> "UserPreferencesUpdate":
        nulled = [f for f in self.model_fields_set if getattr(self, f) is None]
        if nulled:
            raise ValueError(f"{', '.join(sorted(nulled))} cannot be null")
        return self


async def _count_reviews(db: AsyncIOMotorDatabase, username: str) -> int:
    """Reviews this user has completed, across every analysis.

    Deliberately not restricted to latest analyses: reviewing a run that was
    later superseded was still work done, and this is a personal tally rather
    than a measure of outstanding work.
    """
    return await db["case_analysis"].count_documents(
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
    prefs = UserPreferences(**((doc or {}).get("preferences") or {}))
    return await _without_missing_filters(db, prefs, current_user["sub"])


@router.patch(
    "/me/preferences",
    summary="Update current user's preferences",
    responses={
        422: {
            "description": (
                "Invalid preferences, or active_display_filters names a list "
                "that is not a display filter"
            )
        }
    },
)
async def update_my_preferences(
    body: UserPreferencesUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> UserPreferences:
    changes = body.model_dump(exclude_unset=True)
    if "active_display_filters" in changes:
        # Order-preserving de-duplication.
        requested = list(dict.fromkeys(changes["active_display_filters"]))
        found = await taxon_lists.existing_list_ids(
            db, requested, TaxonListKind.DISPLAY_FILTER
        )
        unknown = [list_id for list_id in requested if list_id not in found]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Not display-filter lists: {', '.join(unknown)}",
            )
        changes["active_display_filters"] = requested

    doc = await db["users"].find_one_and_update(
        {"sub": current_user["sub"]},
        {
            "$set": {
                **{f"preferences.{field}": value for field, value in changes.items()},
                "username": current_user["username"],
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return UserPreferences(**(doc.get("preferences") or {}))


async def _without_missing_filters(
    db: AsyncIOMotorDatabase, prefs: UserPreferences, sub: str
) -> UserPreferences:
    """Drop active filters whose list no longer exists.

    Deleting a list removes it from every user's preferences, so this only
    catches drift. Dropping is the safe direction: it shows more taxa, never
    fewer.
    """
    active = prefs.active_display_filters
    found = await taxon_lists.existing_list_ids(
        db, active, TaxonListKind.DISPLAY_FILTER
    )
    missing = [list_id for list_id in active if list_id not in found]
    if not missing:
        return prefs
    logger.warning(
        "User %s has unknown active display filters %s; ignoring them", sub, missing
    )
    return prefs.model_copy(
        update={"active_display_filters": [i for i in active if i in found]}
    )
