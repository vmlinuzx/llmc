"""Reliability middleware for remote LLM API calls.

This module provides production-grade reliability patterns for remote API calls:
- Exponential backoff with jitter for retries
- Token bucket rate limiting (RPM and TPM)
- Circuit breaker for fail-fast behavior
- Cost tracking with budget caps
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Retry Logic with Exponential Backoff
# =============================================================================


def calculate_backoff_delay(
    attempt: int,
    base_seconds: float = 1.0,
    max_delay_seconds: float = 60.0,
    jitter_pct: float = 0.1,
) -> float:
    """Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Retry attempt number (0-indexed)
        base_seconds: Base delay in seconds
        max_delay_seconds: Maximum delay cap
        jitter_pct: Percentage of jitter to add (0.0-1.0)

    Returns:
        Delay in seconds before next retry

    Example:
        >>> calculate_backoff_delay(0)  # ~1s
        >>> calculate_backoff_delay(1)  # ~2s
        >>> calculate_backoff_delay(5)  # ~32s
        >>> calculate_backoff_delay(10) # 60s (capped)
    """
    # Exponential: base * 2^attempt
    delay = min(base_seconds * (2**attempt), max_delay_seconds)

    # Add jitter to prevent thundering herd
    if jitter_pct > 0:
        jitter = random.uniform(0, delay * jitter_pct)
        delay += jitter

    return float(delay)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter_pct: float = 0.1
    retryable_errors: tuple[type[Exception], ...] = ()


class RetryMiddleware:
    """Retry middleware with exponential backoff."""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()
        self._retry_count = 0

    def execute(
        self,
        func: Callable[[], Any],
        *,
        is_retryable: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Execute function with retry logic.

        Args:
            func: Function to execute
            is_retryable: Optional function to determine if error is retryable

        Returns:
            Result from func

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return func()
            except Exception as exc:
                last_exception = exc

                # Check if error is retryable
                retryable = False
                if is_retryable:
                    retryable = is_retryable(exc)
                elif self.config.retryable_errors:
                    retryable = isinstance(exc, self.config.retryable_errors)

                if not retryable:
                    logger.debug(f"Non-retryable error: {exc}")
                    raise

                # Last attempt, no more retries
                if attempt >= self.config.max_retries:
                    logger.warning(
                        f"Max retries ({self.config.max_retries}) exhausted: {exc}"
                    )
                    raise

                # Calculate backoff and wait
                delay = calculate_backoff_delay(
                    attempt,
                    self.config.base_delay,
                    self.config.max_delay,
                    self.config.jitter_pct,
                )

                logger.info(
                    f"Retrying after {delay:.2f}s (attempt {attempt + 1}/{self.config.max_retries}): {exc}"
                )
                self._retry_count += 1
                time.sleep(delay)

        # Should never reach here, but satisfy type checker
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop exited unexpectedly")

    @property
    def retry_count(self) -> int:
        """Total number of retries performed."""
        return self._retry_count


# =============================================================================
# Rate Limiter (Token Bucket)
# =============================================================================


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    tokens_per_minute: int = 1_000_000


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Enforces both requests-per-minute (RPM) and tokens-per-minute (TPM) limits.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._request_times: deque[float] = deque()
        self._token_count = 0
        self._token_window_start = time.monotonic()

    def acquire(self, estimated_tokens: int = 1000) -> float:
        """Calculate delay before request can proceed.

        Args:
            estimated_tokens: Estimated tokens for this request

        Returns:
            Delay in seconds (0 if can proceed immediately)
        """
        now = time.monotonic()

        # Clean up old requests (outside 60s window)
        self._prune_old_requests(now)

        # Check RPM limit
        rpm_wait = 0.0
        if len(self._request_times) >= self.config.requests_per_minute:
            oldest = self._request_times[0]
            rpm_wait = 60.0 - (now - oldest)

        # Check TPM limit
        tpm_wait = 0.0
        if now - self._token_window_start > 60:
            # Reset token window
            self._token_count = 0
            self._token_window_start = now

        if self._token_count + estimated_tokens > self.config.tokens_per_minute:
            tpm_wait = 60.0 - (now - self._token_window_start)

        return max(rpm_wait, tpm_wait, 0.0)

    def record(self, actual_tokens: int) -> None:
        """Record a completed request.

        Args:
            actual_tokens: Actual tokens consumed
        """
        now = time.monotonic()
        self._request_times.append(now)
        self._token_count += actual_tokens

    def _prune_old_requests(self, now: float) -> None:
        """Remove requests older than 60 seconds."""
        cutoff = now - 60.0
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

    def wait_if_needed(self, estimated_tokens: int = 1000) -> None:
        """Block until request can proceed within rate limits.

        Args:
            estimated_tokens: Estimated tokens for this request
        """
        delay = self.acquire(estimated_tokens)
        if delay > 0:
            logger.info(f"Rate limit: waiting {delay:.2f}s before request")
            time.sleep(delay)


# =============================================================================
# Circuit Breaker
# =============================================================================


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Open after N consecutive failures
    recovery_timeout_seconds: float = 60.0  # Try again after N seconds
    half_open_max_attempts: int = 1  # Attempts in half-open state


class CircuitBreaker:
    """Circuit breaker for fail-fast behavior.

    States:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing if service recovered
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._state = self.STATE_CLOSED
        self._half_open_attempts = 0

    def can_proceed(self) -> bool:
        """Check if request can proceed.

        Returns:
            True if request should be attempted
        """
        if self._state == self.STATE_CLOSED:
            return True

        if self._state == self.STATE_OPEN:
            # Check if recovery timeout elapsed
            now = time.monotonic()
            if now - self._last_failure_time > self.config.recovery_timeout_seconds:
                logger.info("Circuit breaker: transitioning to half-open")
                self._state = self.STATE_HALF_OPEN
                self._half_open_attempts = 0
                return True
            return False

        # HALF_OPEN state
        if self._half_open_attempts < self.config.half_open_max_attempts:
            return True
        return False

    def record_success(self) -> None:
        """Record a successful request."""
        if self._state == self.STATE_HALF_OPEN:
            logger.info("Circuit breaker: half-open request succeeded, closing")
            self._state = self.STATE_CLOSED
            self._failure_count = 0
            self._half_open_attempts = 0
        elif self._state == self.STATE_CLOSED:
            self._failure_count = 0
        self._success_count += 1

    def record_failure(self) -> None:
        """Record a failed request."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == self.STATE_HALF_OPEN:
            logger.warning("Circuit breaker: half-open request failed, reopening")
            self._state = self.STATE_OPEN
            self._half_open_attempts = 0
        elif self._state == self.STATE_CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                logger.error(
                    f"Circuit breaker: {self._failure_count} consecutive failures, opening"
                )
                self._state = self.STATE_OPEN

        if self._state == self.STATE_HALF_OPEN:
            self._half_open_attempts += 1

    @property
    def state(self) -> str:
        """Current circuit breaker state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state == self.STATE_OPEN


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


# =============================================================================
# Cost Tracker
# =============================================================================


@dataclass
class PricingInfo:
    """Pricing information for a provider."""

    input_per_million: float  # Cost per 1M input tokens
    output_per_million: float  # Cost per 1M output tokens


@dataclass
class CostTrackerConfig:
    """Configuration for cost tracking."""

    pricing: dict[str, PricingInfo] = field(default_factory=dict)
    daily_cap_usd: float | None = None
    monthly_cap_usd: float | None = None


class CostTracker:
    """Track API spend with optional budget caps."""

    def __init__(self, config: CostTrackerConfig):
        self.config = config
        self._daily_spend = 0.0
        self._monthly_spend = 0.0
        self._day_start = date.today()
        self._month_start = date.today().replace(day=1)
        self._request_count = 0

    def check_budget(self, provider: str, estimated_tokens: int) -> bool:
        """Check if request is within budget.

        Args:
            provider: Provider name
            estimated_tokens: Estimated input tokens

        Returns:
            True if within budget
        """
        self._maybe_reset()

        pricing = self.config.pricing.get(provider)
        if not pricing:
            # No pricing info, allow request
            return True

        est_cost = (estimated_tokens / 1_000_000) * pricing.input_per_million

        if self.config.daily_cap_usd is not None:
            if self._daily_spend + est_cost > self.config.daily_cap_usd:
                logger.error(
                    f"Daily budget cap reached: ${self._daily_spend:.4f} + ${est_cost:.4f} > ${self.config.daily_cap_usd}"
                )
                return False

        if self.config.monthly_cap_usd is not None:
            if self._monthly_spend + est_cost > self.config.monthly_cap_usd:
                logger.error(
                    f"Monthly budget cap reached: ${self._monthly_spend:.4f} + ${est_cost:.4f} > ${self.config.monthly_cap_usd}"
                )
                return False

        return True

    def record(
        self, provider: str, input_tokens: int, output_tokens: int
    ) -> dict[str, Any]:
        """Record actual API usage and cost.

        Args:
            provider: Provider name
            input_tokens: Actual input tokens
            output_tokens: Actual output tokens

        Returns:
            Cost breakdown dict
        """
        self._maybe_reset()

        pricing = self.config.pricing.get(provider)
        if not pricing:
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": 0.0,
                "daily_total": self._daily_spend,
                "monthly_total": self._monthly_spend,
            }

        input_cost = (input_tokens / 1_000_000) * pricing.input_per_million
        output_cost = (output_tokens / 1_000_000) * pricing.output_per_million
        total_cost = input_cost + output_cost

        self._daily_spend += total_cost
        self._monthly_spend += total_cost
        self._request_count += 1

        logger.debug(
            f"Cost: ${total_cost:.6f} (in: {input_tokens}, out: {output_tokens}) | "
            f"Daily: ${self._daily_spend:.4f} | Monthly: ${self._monthly_spend:.4f}"
        )

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "cost_usd": total_cost,
            "daily_total_usd": self._daily_spend,
            "monthly_total_usd": self._monthly_spend,
            "request_count": self._request_count,
        }

    def _maybe_reset(self) -> None:
        """Reset daily/monthly counters if needed."""
        today = date.today()

        # Reset daily counter
        if today != self._day_start:
            logger.info(
                f"Daily cost reset: ${self._daily_spend:.4f} spent on {self._day_start}"
            )
            self._daily_spend = 0.0
            self._day_start = today

        # Reset monthly counter
        month_start = today.replace(day=1)
        if month_start != self._month_start:
            logger.info(
                f"Monthly cost reset: ${self._monthly_spend:.4f} spent in {self._month_start.strftime('%Y-%m')}"
            )
            self._monthly_spend = 0.0
            self._month_start = month_start

    @property
    def daily_spend(self) -> float:
        """Current daily spend."""
        self._maybe_reset()
        return self._daily_spend

    @property
    def monthly_spend(self) -> float:
        """Current monthly spend."""
        self._maybe_reset()
        return self._monthly_spend


class BudgetExceededError(Exception):
    """Raised when budget cap is exceeded."""

    pass


__all__ = [
    "calculate_backoff_delay",
    "RetryConfig",
    "RetryMiddleware",
    "RateLimitConfig",
    "RateLimiter",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerError",
    "PricingInfo",
    "CostTrackerConfig",
    "CostTracker",
    "BudgetExceededError",
]
