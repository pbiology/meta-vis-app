# app/auth/utils.py
#
# Keycloak migration path:
#   1. Set OIDC_ISSUER in .env to your Keycloak realm URL
#   2. Set OIDC_AUDIENCE to your client ID
#   3. Replace _verify_local_token() with python-jose JWKS validation
#   4. Remove the /auth/login endpoint and point the frontend at Keycloak's
#      authorization endpoint directly.

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_minutes: int = 60 * 8) -> str:
    """Create a signed JWT. Subject is the username."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire, "iss": "meta-vis-app"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — inject into any protected endpoint."""
    payload = decode_token(token)
    return {"username": payload["sub"]}