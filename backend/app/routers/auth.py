# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_db
from app.auth.utils import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Obtain a JWT (placeholder for Keycloak)")
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncIOMotorDatabase = Depends(get_db),
):
    user = await db["users"].find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": (user.get("role") or "reader").lower(),
    }


@router.get("/me", summary="Return the current authenticated user")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
