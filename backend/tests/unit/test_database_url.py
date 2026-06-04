import logging

import pytest

from app import database
from app.database import _build_mongo_url, _redact_mongo_url


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
    patched_settings(mongodb_username="a@b", mongodb_password="p/w@:")
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
    patched_settings(mongodb_username="", mongodb_password="pw")
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
    patched_settings(mongodb_username="user", mongodb_password="topsecret")
    with caplog.at_level(logging.INFO, logger="app.database"):
        url = _build_mongo_url()
        database.logger.info("Connecting to MongoDB at %s", _redact_mongo_url(url))
    assert "topsecret" not in caplog.text
    assert "***" in caplog.text
