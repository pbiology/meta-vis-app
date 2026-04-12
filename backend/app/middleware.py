# app/middleware.py

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_logger = logging.getLogger("request")

# Paths that produce no useful signal and would only add noise to logs.
_SKIP_PATHS = frozenset({"/docs", "/openapi.json", "/redoc", "/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, duration, and client IP for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        request_logger.info(
            "%s %s",
            request.method,
            request.url.path,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                # client may be None in test contexts
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response
