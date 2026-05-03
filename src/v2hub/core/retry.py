"""
Retry logic with exponential backoff and circuit breaker.

Provides resilient retry mechanisms for transient failures.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from v2hub.core.exceptions import (
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "RetryConfig",
    "CircuitBreakerConfig",
    "CircuitState",
    "with_retry",
    "with_async_retry",
]

T = TypeVar("T")

# ═══════════════════════════════════════════════════════════════════════════
# Retry Configuration
# ═══════════════════════════════════════════════════════════════════════════

# Errors that should trigger retry
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ServerError,
    ServiceUnavailableError,
    RateLimitError,
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = RETRYABLE_EXCEPTIONS

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt with exponential backoff.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.initial_delay * (self.exponential_base**attempt),
            self.max_delay,
        )

        # Add jitter (±25%)
        if self.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0.0, delay)


# ═══════════════════════════════════════════════════════════════════════════
# Circuit Breaker Pattern
# ═══════════════════════════════════════════════════════════════════════════


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes in half-open to close
    timeout: float = 60.0  # Seconds to wait before half-open
    enabled: bool = True  # Enable/disable circuit breaker


class CircuitBreaker:
    """
    Circuit breaker for preventing cascading failures.

    Tracks failures and temporarily blocks requests to failing services.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        """Initialize circuit breaker."""
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            VPNAPIError: If circuit is open
        """
        if not self.config.enabled:
            return await func(*args, **kwargs)

        async with self._lock:
            # Check if we should transition to half-open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise ServiceUnavailableError(
                        "Circuit breaker is OPEN - service unavailable",
                    )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    logger.info("Circuit breaker transitioning to CLOSED")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker transitioning to OPEN (failure in HALF_OPEN)")
                self.state = CircuitState.OPEN
                self.success_count = 0

            elif self.failure_count >= self.config.failure_threshold:
                logger.warning(
                    f"Circuit breaker transitioning to OPEN "
                    f"({self.failure_count} failures)"
                )
                self.state = CircuitState.OPEN


# ═══════════════════════════════════════════════════════════════════════════
# Async Retry Decorator
# ═══════════════════════════════════════════════════════════════════════════


def with_async_retry(
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for async functions with retry logic.

    Args:
        config: Retry configuration
        circuit_breaker: Optional circuit breaker

    Returns:
        Decorated function

    Example:
        @with_async_retry()
        async def api_call():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    # Use circuit breaker if provided
                    if circuit_breaker:
                        return await circuit_breaker.call(func, *args, **kwargs)
                    return await func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt >= config.max_retries:
                        break

                    # Calculate delay
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = e.retry_after
                    else:
                        delay = config.calculate_delay(attempt)

                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s...",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": config.max_retries + 1,
                            "delay": delay,
                            "exception": type(e).__name__,
                        },
                    )

                    await asyncio.sleep(delay)

            # All retries exhausted
            logger.error(
                f"All {config.max_retries + 1} attempts failed",
                extra={"exception": type(last_exception).__name__ if last_exception else None},
            )
            raise cast(Exception, last_exception)

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# Sync Retry Decorator
# ═══════════════════════════════════════════════════════════════════════════


def with_retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for sync functions with retry logic.

    Args:
        config: Retry configuration

    Returns:
        Decorated function

    Example:
        @with_retry()
        def api_call():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except config.retryable_exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt >= config.max_retries:
                        break

                    # Calculate delay
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = e.retry_after
                    else:
                        delay = config.calculate_delay(attempt)

                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

            # All retries exhausted
            logger.error(f"All {config.max_retries + 1} attempts failed")
            raise cast(Exception, last_exception)

        return wrapper

    return decorator
