# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.audit import log_audit_event
from app.database import get_db
from app.auth.utils import verify_password, create_access_token, get_current_user
from app.auth.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Obtain a JWT via httpOnly cookie")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user = await db["users"].find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        await log_audit_event(
            db,
            action="login_failed",
            actor=form_data.username,
            resource_type="session",
            resource_id=form_data.username,
            outcome="failure",
            detail={"reason": "bad_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user["username"])
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return {
        "username": user["username"],
        "role": (user.get("role") or "reader").lower(),
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"logged_out": True}


@router.get("/me", summary="Return the current authenticated user")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
