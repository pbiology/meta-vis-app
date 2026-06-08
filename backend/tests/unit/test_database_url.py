import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import database
from app.database import _build_mongo_url, _redact_mongo_url, maybe_transaction


@pytest.fixture
def patched_settings(monkeypatch):
    def _patch(**overrides):
        defaults = {
            "mongodb_username": "",
            "mongodb_password": "",
            "mongodb_host": "localhost",
            "mongodb_port": 27017,
            "mongodb_db_name": "meta_vis",
            "mongodb_auth_source": "admin",
            "mongodb_direct_connection": False,
        }
        defaults.update(overrides)
        for key, value in defaults.items():
            monkeypatch.setattr(database.settings, key, value)

    return _patch


def test_build_mongo_url_encodes_special_chars(patched_settings):
    pwd = "p/w@:"
    patched_settings(mongodb_username="a@b", mongodb_password=pwd)
    url = _build_mongo_url()
    assert "a%40b:p%2Fw%40%3A@" in url
    assert "a@b:p/w@:@" not in url


def test_build_mongo_url_no_auth(patched_settings):
    patched_settings()
    url = _build_mongo_url()
    assert url == "mongodb://localhost:27017"


def test_build_mongo_url_user_without_password_raises(patched_settings):
    patched_settings(mongodb_username="user", mongodb_password="")
    with pytest.raises(ValueError):
        _build_mongo_url()


def test_build_mongo_url_password_without_user_raises(patched_settings):
    pwd = "pw"
    patched_settings(mongodb_username="", mongodb_password=pwd)
    with pytest.raises(ValueError):
        _build_mongo_url()


def test_build_mongo_url_direct_connection(patched_settings):
    patched_settings(mongodb_direct_connection=True)
    assert _build_mongo_url().endswith("?directConnection=true")


def test_redact_mongo_url_hides_password():
    url = "mongodb://user:secretpw@host:27017/db?authSource=admin"
    redacted = _redact_mongo_url(url)
    assert "secretpw" not in redacted
    assert "user:***@" in redacted


def test_redact_mongo_url_no_auth_unchanged():
    url = "mongodb://host:27017"
    assert _redact_mongo_url(url) == url


def test_connect_db_logs_redacted_url(patched_settings, caplog):
    pwd = "topsecret"
    patched_settings(mongodb_username="user", mongodb_password=pwd)
    with caplog.at_level(logging.INFO, logger="app.database"):
        url = _build_mongo_url()
        database.logger.info("Connecting to MongoDB at %s", _redact_mongo_url(url))
    assert "topsecret" not in caplog.text
    assert "***" in caplog.text


# ---------------------------------------------------------------------------
# MONGODB_URI override + maybe_transaction
# ---------------------------------------------------------------------------


async def test_connect_db_prefers_mongodb_uri(monkeypatch):
    """When mongodb_uri is set, _build_mongo_url() must be bypassed."""
    captured: dict[str, str] = {}

    def fake_client(url, *args, **kwargs):
        captured["url"] = url
        return MagicMock()

    def fake_make_blob_store(_db):
        return MagicMock()

    monkeypatch.setattr(
        database.settings,
        "mongodb_uri",
        "mongodb://u:p@example.internal:27017/meta-vis?authSource=admin",
    )
    monkeypatch.setattr(database, "AsyncIOMotorClient", fake_client)
    # _ensure_indexes is awaited inside connect_db — AsyncMock gives an
    # awaitable without a bare no-await `async def` helper.
    monkeypatch.setattr(database, "_ensure_indexes", AsyncMock(return_value=None))
    # blob_store import is local inside connect_db — patch at module level.
    import app.blob_store as blob_store

    monkeypatch.setattr(blob_store, "make_blob_store", fake_make_blob_store)

    await database.connect_db()

    assert captured["url"] == (
        "mongodb://u:p@example.internal:27017/meta-vis?authSource=admin"
    )


async def test_maybe_transaction_yields_none_when_disabled(monkeypatch):
    """Standalone mongod: skip start_transaction entirely, yield None."""
    monkeypatch.setattr(database.settings, "mongodb_use_transactions", False)
    client = MagicMock()
    client.start_session = AsyncMock()

    async with maybe_transaction(client) as session:
        assert session is None

    client.start_session.assert_not_called()


async def test_maybe_transaction_starts_transaction_when_enabled(monkeypatch):
    """Replica set: open a session and start a transaction."""
    monkeypatch.setattr(database.settings, "mongodb_use_transactions", True)

    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.start_transaction = MagicMock(return_value=tx_cm)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    client = MagicMock()
    client.start_session = AsyncMock(return_value=session_cm)

    async with maybe_transaction(client) as yielded:
        assert yielded is session

    client.start_session.assert_awaited_once()
    session.start_transaction.assert_called_once()
