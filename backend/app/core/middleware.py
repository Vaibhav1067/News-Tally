"""Cross-cutting HTTP concerns: request logging, body-size limit, rate limiting.

The rate limiter is a per-IP sliding window kept in memory. That is fine for
a single-instance deployment; with several instances you would move it to
Redis (documented in docs/architecture.md).
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

log = logging.getLogger("api")

RATE_LIMITED_PATHS = ("/api/analyze", "/api/feedback")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        # never log request bodies (they may contain user text)
        log.info("%s %s -> %d (%.0f ms)", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - t0) * 1000)
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = get_settings().max_request_bytes
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > limit:
            return JSONResponse(status_code=413, content={"detail": f"Request body exceeds {limit} bytes."})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute: int | None = None):
        super().__init__(app)
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith(RATE_LIMITED_PATHS):
            limit = self.per_minute or get_settings().rate_limit_per_minute
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            q = self.hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                retry = int(60 - (now - q[0])) + 1
                return JSONResponse(status_code=429, headers={"Retry-After": str(retry)},
                                    content={"detail": f"Rate limit exceeded ({limit}/minute). Try again in {retry}s."})
            q.append(now)
        return await call_next(request)
