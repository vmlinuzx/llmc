"""Rate limiting middleware for REST API."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llmc_mcp.transport.utils import get_client_ip

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    tokens: float
    last_update: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting using token bucket algorithm.

    Adds headers to all responses:
    - X-RateLimit-Limit: Requests per minute
    - X-RateLimit-Remaining: Tokens remaining
    - X-RateLimit-Reset: Unix timestamp when bucket refills
    """

    def __init__(
        self,
        app,
        rpm: int = 60,
        burst: int = 10,
        trust_proxy: bool = False,
    ):
        """
        Initialize rate limiter.

        Args:
            app: ASGI app to wrap
            rpm: Requests per minute limit
            burst: Maximum burst size (bucket capacity)
            trust_proxy: Trust X-Forwarded-For for client IP
        """
        super().__init__(app)
        self.rpm = rpm
        self.burst = burst
        self.trust_proxy = trust_proxy
        self.buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(tokens=burst, last_update=time.time())
        )
        self.refill_rate = rpm / 60.0

    def _get_bucket(self, ip: str) -> TokenBucket:
        """Get or create token bucket for IP, applying refill."""
        bucket = self.buckets[ip]
        now = time.time()
        elapsed = now - bucket.last_update

        bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.refill_rate)
        bucket.last_update = now

        return bucket

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limit before forwarding request."""
        client_ip = get_client_ip(request, self.trust_proxy)
        bucket = self._get_bucket(client_ip)

        tokens_needed = self.burst - bucket.tokens
        reset_seconds = tokens_needed / self.refill_rate if tokens_needed > 0 else 0
        reset_time = int(time.time() + reset_seconds)

        if bucket.tokens < 1:
            return JSONResponse(
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Rate limit exceeded. Try again later.",
                        "details": {
                            "retry_after_seconds": int(1 / self.refill_rate),
                        },
                    }
                },
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(self.rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(int(1 / self.refill_rate)),
                },
            )

        bucket.tokens -= 1

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response
