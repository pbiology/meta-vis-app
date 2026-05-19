# app/routers/auth.py
#
# Login and logout are handled directly by Keycloak (the SPA performs the
# OIDC Authorization Code + PKCE flow against the realm). The only endpoint
# left here is /auth/me, which echoes the identity derived from the
# validated access token.

from fastapi import APIRouter, Depends

from app.auth.utils import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", summary="Return the current authenticated user")
async def me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "role": current_user["role"]}
