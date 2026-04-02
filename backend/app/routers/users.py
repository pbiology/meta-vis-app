# app/routers/users.py

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from bson import ObjectId

from app.database import get_db
from app.auth.utils import hash_password, require_role, get_current_user

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = {"reader", "writer", "admin"}

REVIEWER_TITLES = [
    (0,   "Spore"),
    (1,   "Mycelium"),
    (5,   "Puffball"),
    (15,  "Penny Bun"),
    (30,  "Chanterelle"),
    (60,  "Oyster"),
    (100, "Shiitake"),
    (175, "Lion's Mane"),
    (300, "Morel"),
    (500, "Truffle"),
]


def reviewer_title(count: int) -> str:
    title = REVIEWER_TITLES[0][1]
    for threshold, t in REVIEWER_TITLES:
        if count >= threshold:
            title = t
    return title


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
        "_id":            str(doc["_id"]),
        "username":       doc["username"],
        "role":           (doc.get("role") or "reader").lower(),
        "reviews":        reviews,
        "reviewer_title": reviewer_title(reviews),
    }


async def _count_reviews(db: AsyncIOMotorDatabase, username: str) -> int:
    return await db["cases"].count_documents({"review.reviewed_by": username, "review.reviewed": True})


@router.get("", summary="List all users")
async def list_users(
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    docs = await db["users"].find({}, {"password_hash": 0}).to_list(length=200)
    result = []
    for d in docs:
        count = await _count_reviews(db, d["username"])
        result.append(_serialise(d, count))
    return result


@router.get("/me/stats", summary="Get review stats for the current user")
async def get_my_stats(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    count = await _count_reviews(db, current_user["username"])
    return {
        "username":        current_user["username"],
        "reviews":         count,
        "reviewer_title":  reviewer_title(count),
    }


@router.post("", summary="Create a new user")
async def create_user(
    body: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    if body.role.lower() not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Role must be one of: {', '.join(VALID_ROLES)}")
    existing = await db["users"].find_one({"username": body.username})
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' already exists")
    await db["users"].insert_one({
        "username":      body.username,
        "password_hash": hash_password(body.password),
        "role":          body.role.lower(),
    })
    return {"username": body.username, "role": body.role.lower()}


@router.patch("/{username}/role", summary="Update a user's role")
async def update_role(
    username: str,
    body: UserUpdateRole,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    if body.role.lower() not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Role must be one of: {', '.join(VALID_ROLES)}")
    result = await db["users"].update_one(
        {"username": username},
        {"$set": {"role": body.role.lower()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    return {"username": username, "role": body.role.lower()}


@router.patch("/{username}/password", summary="Reset a user's password")
async def update_password(
    username: str,
    body: UserUpdatePassword,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(require_role("admin")),
):
    result = await db["users"].update_one(
        {"username": username},
        {"$set": {"password_hash": hash_password(body.password)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
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
    return {"username": username, "deleted": True}