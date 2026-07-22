"""
Base HTTP client with middleware support.

Provides foundation for making HTTP requests with extensibility through middleware.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from v2hub.core.exceptions import NetworkError, TimeoutError, get_exception_for_status

if TYPE_CHECKING:
    from collections.abc import Callable


logger = logging.getLogger(__name__)

__all__ = ["HTTPClient", "Middleware", "RequestContext"]


# ═══════════════════════════════════════════════════════════════════════════
# Request Context
# ═══════════════════════════════════════════════════════════════════════════


class RequestContext:
    """Context for HTTP request with metadata."""

    def __init__(
        self,
        method: str,
        url: str,
        retries: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize request context.

        Args:
            method: HTTP method
            url: Request URL
            retries: Number of retries attempted
            metadata: Additional metadata
        """
        self.method = method
        self.url = url
        self.retries = retries
        self.metadata = metadata or {}


# ═══════════════════════════════════════════════════════════════════════════
# Middleware Protocol
# ═══════════════════════════════════════════════════════════════════════════


class Middleware:
    """Base middleware for HTTP client."""

    async def __call__(
        self,
        context: RequestContext,
        call_next: Callable[[], Any],
    ) -> httpx.Response:
        """
        Process request/response.

        Args:
            context: Request context
            call_next: Next middleware or actual request

        Returns:
            HTTP response
        """
        response: httpx.Response = await call_next()
        return response


# ═══════════════════════════════════════════════════════════════════════════
# HTTP Client
# ═══════════════════════════════════════════════════════════════════════════


class HTTPClient:
    """
    Base HTTP client with middleware support.

    Provides foundational HTTP functionality with:
    - Automatic error handling
    - Middleware chain
    - Request/response logging
    - Type-safe responses
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        middleware: list[Middleware] | None = None,
    ) -> None:
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            headers: Default headers for all requests
            timeout: Request timeout in seconds
            middleware: List of middleware to apply
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.middleware = middleware or []

        self._client: httpx.AsyncClient | None = None
        self._default_headers = headers or {}

    async def __aenter__(self) -> HTTPClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._default_headers,
                follow_redirects=True,
            )
            logger.debug(f"HTTP client connected to {self.base_url}")

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP client closed")

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make HTTP request with middleware chain.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            **kwargs: Additional request arguments

        Returns:
            HTTP response

        Raises:
            VPNAPIError: On API errors
            NetworkError: On network errors
            TimeoutError: On timeout
        """
        if self._client is None:
            await self.connect()

        context = RequestContext(method=method, url=f"{self.base_url}{path}")

        # Build middleware chain
        async def make_request() -> httpx.Response:
            return await self._execute_request(method, path, **kwargs)

        # Apply middleware in reverse order
        handler = make_request
        for middleware in reversed(self.middleware):
            current_handler = handler

            async def wrapped(
                m: Middleware = middleware,
                h: Callable[[], Any] = current_handler,
            ) -> httpx.Response:
                return await m(context, h)

            handler = wrapped

        return await handler()

    async def _execute_request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute HTTP request with error handling.

        Args:
            method: HTTP method
            path: Request path
            **kwargs: Additional request arguments

        Returns:
            HTTP response

        Raises:
            VPNAPIError: On API errors
            NetworkError: On network errors
            TimeoutError: On timeout
        """
        if self._client is None:
            raise RuntimeError("HTTP client not connected")

        try:
            response = await self._client.request(method, path, **kwargs)

            # Handle error responses
            if response.status_code >= 400:
                await self._handle_error_response(response)

            return response

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {method} {path}")
            raise TimeoutError(f"Request timeout: {e}") from e

        except httpx.NetworkError as e:
            logger.error(f"Network error: {method} {path}")
            raise NetworkError(f"Network error: {e}") from e

        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {method} {path}")
            raise NetworkError(f"HTTP error: {e}") from e

    async def _handle_error_response(self, response: httpx.Response) -> None:
        """
        Handle error response from API.

        Args:
            response: HTTP response

        Raises:
            VPNAPIError: Appropriate exception for error
        """
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except Exception:
            error_data = {}
            message = response.text or f"HTTP {response.status_code}"

        logger.warning(
            f"API error: {response.status_code} - {message}",
            extra={"status_code": response.status_code, "error_data": error_data},
        )

        raise get_exception_for_status(
            status_code=response.status_code,
            message=message,
            response_data=error_data,
        )

    # Convenience methods
    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make PATCH request."""
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make DELETE request."""
        return await self.request("DELETE", path, **kwargs)
