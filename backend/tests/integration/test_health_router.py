# tests/integration/test_health_router.py

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routers import health


@pytest.fixture
def app(fake_db):
    application = FastAPI()
    application.include_router(health.router)
    application.dependency_overrides[get_db] = lambda: fake_db
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def test_live_returns_ok(client):
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_live_unauthenticated(client):
    # No cookies / headers set — liveness must succeed cold.
    res = client.get("/health/live")
    assert res.status_code == 200


async def test_ready_returns_ok_when_db_reachable(client, fake_db):
    await fake_db["cases"].insert_many([{"case_id": "a"}, {"case_id": "b"}])
    await fake_db["samples"].insert_one({"sample_id": "s1"})

    res = client.get("/health/ready")
    assert res.status_code == 200

    body = res.json()
    assert body["status"] == "ok"
    assert body["database"]["reachable"] is True
    assert body["database"]["ping_ms"] is not None
    assert body["collections"]["cases"] == 2
    assert body["collections"]["samples"] == 1
    # Unseeded collections are reported as 0, not omitted.
    assert body["collections"]["users"] == 0


def test_ready_unauthenticated(client):
    res = client.get("/health/ready")
    assert res.status_code == 200


def test_ready_returns_503_when_db_ping_fails(app, client, fake_db, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(fake_db, "command", boom)

    res = client.get("/health/ready")
    assert res.status_code == 503

    body = res.json()
    assert body["status"] == "unavailable"
    assert body["database"]["reachable"] is False
    assert "connection refused" in body["error"]
