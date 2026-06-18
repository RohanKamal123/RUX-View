"""
security_middleware.py — Security hardening layer for Vision OS.

Provides CORS, rate limiting, HTTPS redirect, request ID tracing,
security headers, and middleware registration for public SaaS access.

Key decisions:
- D012: Firebase Auth for authentication
- D026: All calls async
- Rate limiting at application layer (complementing Cloud Armor)
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_at: int  # unix timestamp
    retry_after: Optional[int] = None  # seconds


@dataclass
class RateLimitStats:
    """Statistics for the rate limiter."""

    total_requests_tracked: int
    blocked_requests: int
    active_ips: int
    top_endpoints: list[tuple[str, int]]


# ── RateLimiter ─────────────────────────────────────────────────


class RateLimiter:
    """Application-layer rate limiter with per-endpoint limits.

    Uses a sliding window approach with in-memory tracking.
    Endpoint-specific limits:
    - /api/auth/*: 10 requests/min per IP
    - /api/signup: 5 requests/min per IP
    - /api/*: 100 requests/min per IP
    - /static/*: 300 requests/min per IP
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.default_max_requests = max_requests
        self.default_window_seconds = window_seconds
        # {ip: {endpoint: [(timestamp, ...)]}}
        self._requests: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._blocked_count: int = 0
        self._total_count: int = 0

        # Endpoint-specific limits
        self._endpoint_limits: dict[str, tuple[int, int]] = {
            "/api/auth/": (10, 60),  # 10 requests per 60 seconds
            "/api/signup": (5, 60),  # 5 requests per 60 seconds
            "/api/": (100, 60),  # 100 requests per 60 seconds
            "/static/": (300, 60),  # 300 requests per 60 seconds
        }

    def _get_limit_for_endpoint(self, endpoint: str) -> tuple[int, int]:
        """Get the rate limit for a specific endpoint.

        Args:
            endpoint: The request endpoint path.

        Returns:
            Tuple of (max_requests, window_seconds).
        """
        for prefix, limit in self._endpoint_limits.items():
            if endpoint.startswith(prefix):
                return limit
        return (self.default_max_requests, self.default_window_seconds)

    async def check_rate_limit(self, ip: str, endpoint: str) -> RateLimitResult:
        """Check if a request is within the rate limit.

        Args:
            ip: Client IP address.
            endpoint: Request endpoint path.

        Returns:
            RateLimitResult with allowed status and details.
        """
        max_req, window_sec = self._get_limit_for_endpoint(endpoint)
        now = time.time()
        window_start = now - window_sec

        # Clean old entries for this IP+endpoint
        self._requests[ip][endpoint] = [
            ts for ts in self._requests[ip][endpoint] if ts > window_start
        ]

        current_count = len(self._requests[ip][endpoint])
        self._total_count += 1

        if current_count >= max_req:
            self._blocked_count += 1
            oldest = self._requests[ip][endpoint][0] if self._requests[ip][endpoint] else now
            reset_at = int(oldest + window_sec)
            retry_after = max(0, int(reset_at - now))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        self._requests[ip][endpoint].append(now)
        remaining = max_req - current_count - 1
        reset_at = int(now + window_sec)

        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_at=reset_at,
        )

    async def get_remaining(self, ip: str, endpoint: str) -> int:
        """Get remaining requests for an IP+endpoint.

        Args:
            ip: Client IP address.
            endpoint: Request endpoint path.

        Returns:
            Number of remaining requests.
        """
        max_req, window_sec = self._get_limit_for_endpoint(endpoint)
        now = time.time()
        window_start = now - window_sec

        self._requests[ip][endpoint] = [
            ts for ts in self._requests[ip][endpoint] if ts > window_start
        ]
        current_count = len(self._requests[ip][endpoint])
        return max(0, max_req - current_count)

    async def get_reset_time(self, ip: str, endpoint: str) -> int:
        """Get the reset time (unix timestamp) for an IP+endpoint.

        Args:
            ip: Client IP address.
            endpoint: Request endpoint path.

        Returns:
            Unix timestamp when the rate limit resets.
        """
        _, window_sec = self._get_limit_for_endpoint(endpoint)
        now = time.time()
        window_start = now - window_sec

        self._requests[ip][endpoint] = [
            ts for ts in self._requests[ip][endpoint] if ts > window_start
        ]
        if self._requests[ip][endpoint]:
            return int(self._requests[ip][endpoint][0] + window_sec)
        return int(now + window_sec)

    async def reset_limit(self, ip: str, endpoint: str) -> dict:
        """Reset the rate limit for an IP+endpoint.

        Args:
            ip: Client IP address.
            endpoint: Request endpoint path.

        Returns:
            Dict with reset status.
        """
        if ip in self._requests and endpoint in self._requests[ip]:
            del self._requests[ip][endpoint]
        return {"status": "reset", "ip": ip, "endpoint": endpoint}

    async def get_rate_limit_stats(self) -> RateLimitStats:
        """Get overall rate limiter statistics.

        Returns:
            RateLimitStats with tracking data.
        """
        active_ips = len(self._requests)
        # Count top endpoints
        endpoint_counts: dict[str, int] = {}
        for ip_data in self._requests.values():
            for ep, timestamps in ip_data.items():
                endpoint_counts[ep] = endpoint_counts.get(ep, 0) + len(timestamps)

        top_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return RateLimitStats(
            total_requests_tracked=self._total_count,
            blocked_requests=self._blocked_count,
            active_ips=active_ips,
            top_endpoints=top_endpoints,
        )


# ── Global rate limiter instance ────────────────────────────────

_rate_limiter = RateLimiter()


# ── Middleware Functions ─────────────────────────────────────────


def cors_middleware(app: FastAPI) -> None:
    """Add CORS middleware allowing all origins (public SaaS).

    Args:
        app: FastAPI application instance.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )
    logger.info("CORS middleware configured: allow all origins")


def rate_limit_middleware(app: FastAPI) -> None:
    """Add rate limiting middleware.

    Args:
        app: FastAPI application instance.
    """

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            # Skip rate limiting for health checks
            if request.url.path == "/health":
                return await call_next(request)

            # Get client IP
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else "unknown"

            # Check rate limit
            result = await _rate_limiter.check_rate_limit(ip, request.url.path)

            if not result.allowed:
                logger.warning(
                    "Rate limit exceeded for IP: %s, endpoint: %s, reset_at: %d",
                    ip, request.url.path, result.reset_at,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please try again later.",
                        "retry_after": result.retry_after,
                        "reset_at": result.reset_at,
                    },
                    headers={
                        "Retry-After": str(result.retry_after or 60),
                        "X-RateLimit-Limit": "100",
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(result.reset_at),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = "100"
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset_at)

            return response

    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limit middleware configured")


def https_redirect_middleware(app: FastAPI) -> None:
    """Add HTTPS redirect middleware (redirect HTTP → HTTPS).

    Args:
        app: FastAPI application instance.
    """

    class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            # Only redirect if not already HTTPS and not on localhost
            if (
                request.url.scheme == "http"
                and request.headers.get("X-Forwarded-Proto") != "https"
                and request.url.hostname not in ("localhost", "127.0.0.1")
            ):
                redirect_url = str(request.url).replace("http://", "https://", 1)
                logger.info("Redirecting HTTP → HTTPS: %s", redirect_url)
                return RedirectResponse(url=redirect_url, status_code=301)

            return await call_next(request)

    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS redirect middleware configured")


def request_id_middleware(app: FastAPI) -> None:
    """Add request ID tracing middleware.

    Args:
        app: FastAPI application instance.
    """

    class RequestIDMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            request.state.request_id = request_id

            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            return response

    app.add_middleware(RequestIDMiddleware)
    logger.info("Request ID middleware configured")


def security_headers_middleware(app: FastAPI) -> None:
    """Add security headers to all responses.

    Args:
        app: FastAPI application instance.
    """

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            response = await call_next(request)

            # Security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://apis.google.com; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self'; "
                "connect-src 'self' https://*.firebaseio.com wss://*.firebaseio.com; "
                "frame-src 'none'; "
                "object-src 'none'"
            )
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=()"
            )

            return response

    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware configured")


def add_all_middleware(app: FastAPI) -> None:
    """Add all security middleware to the FastAPI application.

    Order matters — middleware is applied in reverse order of addition.
    We add in the order we want them to execute (outermost first).

    Args:
        app: FastAPI application instance.
    """
    # These execute in reverse order (last added = first executed)
    cors_middleware(app)           # 1. CORS (outermost)
    https_redirect_middleware(app)  # 2. HTTPS redirect
    request_id_middleware(app)     # 3. Request ID
    security_headers_middleware(app)  # 4. Security headers
    rate_limit_middleware(app)     # 5. Rate limiting (innermost)

    logger.info("All security middleware registered")


# ── Convenience exports ─────────────────────────────────────────

__all__ = [
    "RateLimiter",
    "RateLimitResult",
    "RateLimitStats",
    "cors_middleware",
    "rate_limit_middleware",
    "https_redirect_middleware",
    "request_id_middleware",
    "security_headers_middleware",
    "add_all_middleware",
    "_rate_limiter",
]
