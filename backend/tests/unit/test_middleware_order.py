# tests/unit/test_middleware_order.py

from starlette.middleware.cors import CORSMiddleware

from app.main import app


def test_cors_is_outermost_middleware():
    """CORS must wrap every other middleware so all responses get CORS headers.

    Starlette keeps ``user_middleware`` outermost-first, so CORS (the last one
    added in ``main.py``) must be at index 0.
    """
    assert app.user_middleware[0].cls is CORSMiddleware
