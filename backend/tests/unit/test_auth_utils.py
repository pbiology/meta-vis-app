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

# ---------------------------------------------------------------------------
# get_current_user — user not in DB defaults role to reader
# ---------------------------------------------------------------------------

async def test_get_current_user_unknown_user_defaults_to_reader():
    from mongomock_motor import AsyncMongoMockClient
    from app.auth.utils import get_current_user, create_access_token
    token = create_access_token("ghost_user")
    db = AsyncMongoMockClient()["test_db"]
    result = await get_current_user(access_token=token, db=db)
    assert result["username"] == "ghost_user"
    assert result["role"] == "reader"


async def test_get_current_user_known_user_returns_correct_role():
    from mongomock_motor import AsyncMongoMockClient
    from app.auth.utils import get_current_user, create_access_token, hash_password
    db = AsyncMongoMockClient()["test_db"]
    await db["users"].insert_one({
        "username": "alice", "password_hash": hash_password("secret"), "role": "admin"
    })
    token = create_access_token("alice")
    result = await get_current_user(access_token=token, db=db)
    assert result["role"] == "admin"