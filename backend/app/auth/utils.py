# app/auth/utils.py
#
# Keycloak OIDC access-token validation. Tokens arrive in the
# `Authorization: Bearer …` header; signatures are checked against the
# realm's JWKS (cached by pyjwt).

from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from app.config import settings

ALGORITHMS = ["RS256"]
ROLE_PRIORITY = ["admin", "writer", "reader"]


def _jwks_url() -> str:
    if settings.keycloak_jwks_url:
        return settings.keycloak_jwks_url
    return f"{settings.keycloak_issuer.rstrip('/')}/protocol/openid-connect/certs"


# Module-level JWKS client so the realm's signing keys are fetched once and
# reused. PyJWKClient handles key rotation transparently via the `kid` header.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_jwks_url(), cache_keys=True)
    return _jwks_client


def _highest_role(realm_roles: list[str]) -> str:
    lowered = {r.lower() for r in realm_roles}
    for role in ROLE_PRIORITY:
        if role in lowered:
            return role
    return "reader"


def verify_access_token(token: str) -> dict:
    """Validate a Keycloak access token and return its claims."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
        # Keycloak emits `aud` based on the user's resource client roles —
        # e.g. a user with realm-management roles gets aud=realm-management.
        # That makes a fixed expected audience brittle; replay protection
        # comes from validating `azp` (the client the token was issued for).
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=ALGORITHMS,
            issuer=settings.keycloak_issuer,
            options={"require": ["exp", "iss", "sub", "azp"], "verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    allowed_clients = {
        c.strip() for c in settings.keycloak_client_ids.split(",") if c.strip()
    }
    if claims.get("azp") not in allowed_clients:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token was not issued for this client",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    claims = verify_access_token(token)
    resource_access = claims.get("resource_access") or {}
    client_roles = (resource_access.get(settings.keycloak_role_client) or {}).get(
        "roles"
    ) or []
    return {
        "sub": claims["sub"],
        "username": claims.get("preferred_username") or claims["sub"],
        "role": _highest_role(client_roles),
    }


def require_role(*roles: str):
    """Dependency factory — raises 403 if the user's role is not in the allowed set."""
    allowed = {r.lower() for r in roles}

    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return _check
