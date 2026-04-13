# app/routers/users.py

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, field_validator

from app.audit import log_audit_event
from app.database import get_db
from app.auth.utils import hash_password, require_role, get_current_user

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = {"reader", "writer", "admin"}

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


class UserPreferences(BaseModel):
    preferred_kingdoms: list[str] = ["Viruses"]

    @field_validator("preferred_kingdoms")
    @classmethod
    def kingdoms_must_be_valid(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_KINGDOMS
        if invalid:
            raise ValueError(f"Invalid kingdoms: {invalid}")
        return v


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "reader"


class UserUpdateRole(BaseModel):
    role: str


class UserUpdatePassword(BaseModel):
    password: str


def _serialise(doc: dict, reviews: int = 0) -> dict:
    return {
        "_id": str(doc["_id"]),
        "username": doc["username"],
        "role": (doc.get("role") or "reader").lower(),
        "reviews": reviews,
        "reviewer_title": reviewer_title(reviews),
    }


async def _count_reviews(db: AsyncIOMotorDatabase, username: str) -> int:
    return await db["cases"].count_documents(
        {"review.reviewed_by": username, "review.reviewed": True}
    )


@router.get("", summary="List all users")
async def list_users(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    docs = await db["users"].find({}, {"password_hash": 0}).to_list(length=200)  # nosec B105

    # Single aggregation to get all review counts at once
    pipeline: list[dict] = [
        {"$match": {"review.reviewed": True}},
        {"$group": {"_id": "$review.reviewed_by", "count": {"$sum": 1}}},
    ]
    counts_raw = await db["cases"].aggregate(pipeline).to_list(length=500)
    review_counts = {doc["_id"]: doc["count"] for doc in counts_raw}

    return [_serialise(d, review_counts.get(d["username"], 0)) for d in docs]


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
    doc = await db["users"].find_one(
        {"username": current_user["username"]}, {"preferences": 1}
    )
    prefs: dict = (doc or {}).get("preferences") or {}
    return UserPreferences(**prefs)


@router.patch("/me/preferences", summary="Update current user's preferences")
async def update_my_preferences(
    body: UserPreferences,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> UserPreferences:
    await db["users"].update_one(
        {"username": current_user["username"]},
        {"$set": {"preferences": body.model_dump()}},
    )
    return body


@router.post("", summary="Create a new user")
async def create_user(
    body: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    if body.role.lower() not in VALID_ROLES:
        raise HTTPException(
            status_code=422, detail=f"Role must be one of: {', '.join(VALID_ROLES)}"
        )
    existing = await db["users"].find_one({"username": body.username})
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Username '{body.username}' already exists"
        )
    await db["users"].insert_one(
        {
            "username": body.username,
            "password_hash": hash_password(body.password),
            "role": body.role.lower(),
        }
    )
    await log_audit_event(
        db,
        action="user_create",
        actor=current_user["username"],
        resource_type="user",
        resource_id=body.username,
        outcome="success",
        detail={"role": body.role.lower()},
    )
    return {"username": body.username, "role": body.role.lower()}


@router.patch("/{username}/role", summary="Update a user's role")
async def update_role(
    username: str,
    body: UserUpdateRole,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    if body.role.lower() not in VALID_ROLES:
        raise HTTPException(
            status_code=422, detail=f"Role must be one of: {', '.join(VALID_ROLES)}"
        )
    result = await db["users"].update_one(
        {"username": username},
        {"$set": {"role": body.role.lower()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    await log_audit_event(
        db,
        action="user_role_change",
        actor=current_user["username"],
        resource_type="user",
        resource_id=username,
        outcome="success",
        detail={"new_role": body.role.lower()},
    )
    return {"username": username, "role": body.role.lower()}


@router.patch("/{username}/password", summary="Reset a user's password")
async def update_password(
    username: str,
    body: UserUpdatePassword,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    result = await db["users"].update_one(
        {"username": username},
        {"$set": {"password_hash": hash_password(body.password)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    await log_audit_event(
        db,
        action="user_password_reset",
        actor=current_user["username"],
        resource_type="user",
        resource_id=username,
        outcome="success",
    )
    return {"username": username, "updated": True}


@router.delete("/{username}", summary="Delete a user")
async def delete_user(
    username: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    result = await db["users"].delete_one({"username": username})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    await log_audit_event(
        db,
        action="user_delete",
        actor=current_user["username"],
        resource_type="user",
        resource_id=username,
        outcome="success",
    )
    return {"username": username, "deleted": True}
