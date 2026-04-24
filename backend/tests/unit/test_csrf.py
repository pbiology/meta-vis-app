import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    verify_csrf,
)


def _make_app() -> FastAPI:
    app = FastAPI(dependencies=[Depends(verify_csrf)])

    @app.get("/api/v1/thing")
    async def get_thing():
        return {"ok": True}

    @app.post("/api/v1/thing")
    async def post_thing():
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"logged_in": True}

    return app


def test_generate_csrf_token_is_unique_and_nontrivial():
    a = generate_csrf_token()
    b = generate_csrf_token()
    assert a != b
    assert len(a) >= 32


def test_get_passes_without_csrf():
    client = TestClient(_make_app())
    res = client.get("/api/v1/thing")
    assert res.status_code == 200


def test_post_without_header_is_forbidden():
    client = TestClient(_make_app())
    client.cookies.set(CSRF_COOKIE_NAME, "abc")
    res = client.post("/api/v1/thing")
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]


def test_post_without_cookie_is_forbidden():
    client = TestClient(_make_app())
    res = client.post("/api/v1/thing", headers={CSRF_HEADER_NAME: "abc"})
    assert res.status_code == 403


def test_post_with_mismatched_token_is_forbidden():
    client = TestClient(_make_app())
    client.cookies.set(CSRF_COOKIE_NAME, "cookie-value")
    res = client.post("/api/v1/thing", headers={CSRF_HEADER_NAME: "header-value"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Invalid CSRF token"


def test_post_with_matching_token_succeeds():
    client = TestClient(_make_app())
    token = "matching-token-123"
    client.cookies.set(CSRF_COOKIE_NAME, token)
    res = client.post("/api/v1/thing", headers={CSRF_HEADER_NAME: token})
    assert res.status_code == 200


def test_login_endpoint_is_exempt():
    client = TestClient(_make_app())
    res = client.post("/api/v1/auth/login")
    assert res.status_code == 200


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_all_unsafe_methods_require_csrf(method: str):
    app = FastAPI(dependencies=[Depends(verify_csrf)])

    @app.api_route("/api/v1/thing", methods=[method])
    async def handler():
        return {"ok": True}

    client = TestClient(app)
    res = client.request(method, "/api/v1/thing")
    assert res.status_code == 403


async def test_verify_csrf_dependency_direct_safe_method():
    """Direct call: safe method returns None without raising."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/thing",
        "headers": [],
    }
    request = Request(scope)
    assert await verify_csrf(request) is None


async def test_verify_csrf_dependency_direct_unsafe_missing():
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/thing",
        "headers": [],
    }
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        await verify_csrf(request)
    assert exc.value.status_code == 403
