# tests/unit/test_auth_utils.py
#
# Exercises Keycloak access-token validation. We sign tokens locally with an
# in-test RSA keypair and monkeypatch the JWKS client so the public key is
# returned without any HTTP call.

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import utils as auth_utils
from app.config import settings


@pytest.fixture
def rsa_keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def patched_jwks(monkeypatch, rsa_keypair):
    """Patch the JWKS client so signature verification uses the test key."""

    def fake_get_signing_key_from_jwt(self, _token):
        return SimpleNamespace(key=rsa_keypair.public_key())

    monkeypatch.setattr(
        "jwt.PyJWKClient.get_signing_key_from_jwt",
        fake_get_signing_key_from_jwt,
    )
    monkeypatch.setattr(auth_utils, "_jwks_client", None)
    yield


def _make_token(
    key,
    *,
    sub: str = "user-uuid",
    preferred_username: str = "alice",
    roles: list[str] | None = None,
    azp: str | None = None,
    aud: str | None = None,
    iss: str | None = None,
    expires_in: int = 300,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "preferred_username": preferred_username,
        "azp": azp or settings.keycloak_client_ids.split(",")[0],
        "aud": aud or "account",
        "iss": iss or settings.keycloak_issuer,
        "iat": now,
        "exp": now + expires_in,
        "resource_access": {
            settings.keycloak_role_client: {"roles": roles or ["reader"]}
        },
    }
    return jwt.encode(payload, key, algorithm="RS256")


# ---------------------------------------------------------------------------
# verify_access_token
# ---------------------------------------------------------------------------


def test_valid_token_returns_claims(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, sub="u1", preferred_username="alice")
    claims = auth_utils.verify_access_token(token)
    assert claims["sub"] == "u1"
    assert claims["preferred_username"] == "alice"


def test_expired_token_rejected(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, expires_in=-10)
    with pytest.raises(HTTPException) as exc:
        auth_utils.verify_access_token(token)
    assert exc.value.status_code == 401


def test_wrong_azp_rejected(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, azp="some-other-client")
    with pytest.raises(HTTPException) as exc:
        auth_utils.verify_access_token(token)
    assert exc.value.status_code == 401


def test_wrong_issuer_rejected(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, iss="http://evil.example/realms/x")
    with pytest.raises(HTTPException) as exc:
        auth_utils.verify_access_token(token)
    assert exc.value.status_code == 401


def test_tampered_signature_rejected(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair)
    tampered = token[:-5] + ("A" if token[-1] != "A" else "B") * 5
    with pytest.raises(HTTPException) as exc:
        auth_utils.verify_access_token(tampered)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


def test_get_current_user_extracts_identity_and_role(rsa_keypair, patched_jwks):
    token = _make_token(
        rsa_keypair,
        sub="u-42",
        preferred_username="bob",
        roles=["reader", "writer"],
    )
    result = auth_utils.get_current_user(authorization=f"Bearer {token}")
    assert result == {"sub": "u-42", "username": "bob", "role": "writer"}


def test_get_current_user_picks_highest_role(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, roles=["reader", "writer", "admin"])
    result = auth_utils.get_current_user(authorization=f"Bearer {token}")
    assert result["role"] == "admin"


def test_get_current_user_falls_back_to_reader_when_no_client_roles(
    rsa_keypair, patched_jwks
):
    token = _make_token(rsa_keypair, roles=[])
    result = auth_utils.get_current_user(authorization=f"Bearer {token}")
    assert result["role"] == "reader"


def test_get_current_user_uses_sub_when_username_missing(rsa_keypair, patched_jwks):
    token = _make_token(rsa_keypair, sub="u-9", preferred_username="")
    result = auth_utils.get_current_user(authorization=f"Bearer {token}")
    assert result["username"] == "u-9"


def test_get_current_user_missing_header_raises_401():
    with pytest.raises(HTTPException) as exc:
        auth_utils.get_current_user(authorization=None)
    assert exc.value.status_code == 401


def test_get_current_user_non_bearer_header_raises_401():
    with pytest.raises(HTTPException) as exc:
        auth_utils.get_current_user(authorization="Basic abc")
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------


def test_require_role_allows_matching_role():
    user = {"sub": "s", "username": "u", "role": "writer"}
    dep = auth_utils.require_role("writer", "admin")
    assert dep(current_user=user) == user


def test_require_role_blocks_other_role():
    user = {"sub": "s", "username": "u", "role": "reader"}
    dep = auth_utils.require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(current_user=user)
    assert exc.value.status_code == 403
