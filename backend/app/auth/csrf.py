# app/auth/csrf.py

import hmac
import secrets

from fastapi import HTTPException, Request, status

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Paths exempt from CSRF verification. Login cannot have a CSRF cookie yet;
# it relies on user credentials for authentication.
EXEMPT_PATHS = {"/api/v1/auth/login"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


async def verify_csrf(request: Request) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    if request.url.path in EXEMPT_PATHS:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token",
        )
    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
