# tests/unit/test_auth_utils.py

import pytest
from app.auth.utils import hash_password, verify_password, create_access_token, decode_token
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------

def test_hash_password_returns_string():
    result = hash_password("mysecret")
    assert isinstance(result, str)


def test_hash_password_is_not_plaintext():
    result = hash_password("mysecret")
    assert result != "mysecret"


def test_hash_password_different_hashes_for_same_input():
    # bcrypt uses a random salt so two hashes of the same password differ
    h1 = hash_password("mysecret")
    h2 = hash_password("mysecret")
    assert h1 != h2


def test_verify_password_correct():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_empty_string():
    hashed = hash_password("mysecret")
    assert verify_password("", hashed) is False


# ---------------------------------------------------------------------------
# create_access_token / decode_token
# ---------------------------------------------------------------------------

def test_create_access_token_returns_string():
    token = create_access_token("testuser")
    assert isinstance(token, str)


def test_decode_token_returns_correct_subject():
    token = create_access_token("testuser")
    payload = decode_token(token)
    assert payload["sub"] == "testuser"


def test_decode_token_contains_exp():
    token = create_access_token("testuser")
    payload = decode_token(token)
    assert "exp" in payload


def test_decode_token_contains_iss():
    token = create_access_token("testuser")
    payload = decode_token(token)
    assert payload["iss"] == "meta-vis-app"


def test_decode_token_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("this.is.not.a.valid.token")
    assert exc_info.value.status_code == 401


def test_decode_token_tampered_token_raises_401():
    token = create_access_token("testuser")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(HTTPException) as exc_info:
        decode_token(tampered)
    assert exc_info.value.status_code == 401


def test_roundtrip_different_usernames():
    for username in ["alice", "bob", "admin_user"]:
        token = create_access_token(username)
        payload = decode_token(token)
        assert payload["sub"] == username