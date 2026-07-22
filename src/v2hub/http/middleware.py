"""
Middleware for HTTP client.

Provides logging, metrics, and request/response transformation.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from .client import Middleware, RequestContext

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx


logger = logging.getLogger(__name__)

__all__ = ["LoggingMiddleware", "MetricsMiddleware", "RetryMiddleware"]


# ═══════════════════════════════════════════════════════════════════════════
# Logging Middleware
# ═══════════════════════════════════════════════════════════════════════════


class LoggingMiddleware(Middleware):
    """Middleware for request/response logging."""

    def __init__(self, log_level: int = logging.DEBUG) -> None:
        """
        Initialize logging middleware.

        Args:
            log_level: Logging level for requests
        """
        self.log_level = log_level

    async def __call__(
        self,
        context: RequestContext,
        call_next: Callable[[], Any],
    ) -> httpx.Response:
        """Log request and response."""
        # Log request
        logger.log(
            self.log_level,
            f"→ {context.method} {context.url}",
            extra={
                "method": context.method,
                "url": context.url,
                "retries": context.retries,
            },
        )

        start_time = time.time()

        try:
            response: httpx.Response = await call_next()

            # Log response
            duration = time.time() - start_time
            logger.log(
                self.log_level,
                f"← {response.status_code} {context.method} {context.url} ({duration:.3f}s)",
                extra={
                    "method": context.method,
                    "url": context.url,
                    "status_code": response.status_code,
                    "duration": duration,
                },
            )

            return response

        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(
                f"✗ {context.method} {context.url} failed ({duration:.3f}s): {e}",
                extra={
                    "method": context.method,
                    "url": context.url,
                    "duration": duration,
                    "error": str(e),
                },
            )
            raise


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Middleware
# ═══════════════════════════════════════════════════════════════════════════


class MetricsMiddleware(Middleware):
    """Middleware for collecting request metrics."""

    def __init__(self) -> None:
        """Initialize metrics middleware."""
        self.request_count = 0
        self.error_count = 0
        self.total_duration = 0.0

    async def __call__(
        self,
        context: RequestContext,
        call_next: Callable[[], Any],
    ) -> httpx.Response:
        """Collect metrics."""
        self.request_count += 1
        start_time = time.time()

        try:
            response: httpx.Response = await call_next()
            duration = time.time() - start_time
            self.total_duration += duration
            return response

        except Exception:
            self.error_count += 1
            duration = time.time() - start_time
            self.total_duration += duration
            raise

    @property
    def average_duration(self) -> float:
        """Get average request duration."""
        if self.request_count == 0:
            return 0.0
        return self.total_duration / self.request_count

    @property
    def error_rate(self) -> float:
        """Get error rate."""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics."""
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "total_duration": self.total_duration,
            "average_duration": self.average_duration,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Retry Middleware
# ═══════════════════════════════════════════════════════════════════════════


class RetryMiddleware(Middleware):
    """Middleware for tracking retry attempts."""

    async def __call__(
        self,
        context: RequestContext,
        call_next: Callable[[], Any],
    ) -> httpx.Response:
        """Track retry attempts in context."""
        # This middleware mainly updates context
        # Actual retry logic is in retry.py decorators
        response: httpx.Response = await call_next()
        return response
