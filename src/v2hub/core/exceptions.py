"""
Custom exceptions for VPN Subscription API client.

Comprehensive exception hierarchy with error context and recovery hints.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "VPNAPIError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "ServiceUnavailableError",
    "NetworkError",
    "TimeoutError",
    "InvalidURLError",
    "InvalidConfigError",
    "SubscriptionNotFoundError",
    "SourceNotFoundError",
    "DuplicateNameError",
    "CircularReferenceError",
    "NestingTooDeepError",
    "TooManyConfigsError",
    "TooManySourcesError",
    "TooManySubscriptionsError",
    "ExternalFetchError",
    "CacheError",
    "get_exception_for_status",
]


# ═══════════════════════════════════════════════════════════════════════════
# Base Exception
# ═══════════════════════════════════════════════════════════════════════════


class VPNAPIError(Exception):
    """Base exception for all VPN API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        """
        Initialize VPN API error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            response_data: Raw response data from API
            retry_after: Seconds to wait before retry (for rate limits)
        """
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.retry_after = retry_after
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation with status code."""
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"retry_after={self.retry_after})"
        )

    @property
    def is_retryable(self) -> bool:
        """Check if error is retryable."""
        return isinstance(
            self,
            (TimeoutError, ServerError, ServiceUnavailableError, RateLimitError),
        )

    @property
    def recovery_hint(self) -> str:
        """Get recovery hint for this error."""
        hints = {
            ValidationError: "Check request parameters and fix validation errors",
            AuthenticationError: "Verify API token is valid and not expired",
            NotFoundError: "Ensure the resource exists and token/name is correct",
            ConflictError: "Resource already exists - use update or choose different name",
            RateLimitError: "Wait before retrying - rate limit exceeded",
            ServerError: "Temporary server error - retry after delay",
            ServiceUnavailableError: "Service temporarily unavailable - retry later",
            NetworkError: "Check network connectivity and retry",
            TimeoutError: "Request timed out - retry with longer timeout",
        }
        return hints.get(type(self), "Contact API support if problem persists")


# ═══════════════════════════════════════════════════════════════════════════
# Client Errors (4xx)
# ═══════════════════════════════════════════════════════════════════════════


class ValidationError(VPNAPIError):
    """Request validation failed (400)."""

    pass


class AuthenticationError(VPNAPIError):
    """Invalid or missing API token (401)."""

    pass

class AuthorizationError(VPNAPIError):
    """Insufficient permissions for the requested operation (403)."""

    pass


class NotFoundError(VPNAPIError):
    """Resource not found (404)."""

    pass


class ConflictError(VPNAPIError):
    """Resource already exists (409)."""

    pass


class RateLimitError(VPNAPIError):
    """Rate limit exceeded (429)."""

    @property
    def recovery_hint(self) -> str:
        """Get recovery hint with retry_after info."""
        if self.retry_after:
            return f"Rate limited - wait {self.retry_after} seconds before retrying"
        return "Rate limited - wait before retrying"


# ═══════════════════════════════════════════════════════════════════════════
# Server Errors (5xx)
# ═══════════════════════════════════════════════════════════════════════════


class ServerError(VPNAPIError):
    """Internal server error (500)."""

    pass


class ServiceUnavailableError(VPNAPIError):
    """Service temporarily unavailable (503)."""

    pass


# ═══════════════════════════════════════════════════════════════════════════
# Network/Connection Errors
# ═══════════════════════════════════════════════════════════════════════════


class NetworkError(VPNAPIError):
    """Network connection error."""

    pass


class TimeoutError(VPNAPIError):
    """Request timeout."""

    pass


# ═══════════════════════════════════════════════════════════════════════════
# Business Logic Errors
# ═══════════════════════════════════════════════════════════════════════════


class InvalidURLError(ValidationError):
    """Invalid URL provided (SSRF protection triggered)."""

    @property
    def recovery_hint(self) -> str:
        """Get recovery hint for invalid URL."""
        return "URL validation failed - ensure URL is publicly accessible and not internal/local"


class SubscriptionNotFoundError(NotFoundError):
    """Subscription not found by token or name."""

    @property
    def recovery_hint(self) -> str:
        """Get recovery hint for missing subscription."""
        return "Subscription not found - verify token/name or create new subscription"


class SourceNotFoundError(NotFoundError):
    """Source not found by ID."""

    @property
    def recovery_hint(self) -> str:
        """Get recovery hint for missing source."""
        return "Source not found - verify source ID exists in subscription"


class InvalidConfigError(VPNAPIError):
    """Invalid configuration format or unsupported structure."""

    pass


class DuplicateNameError(VPNAPIError):
    """Configuration with the same name already exists."""

    pass


class CircularReferenceError(VPNAPIError):
    """Circular dependency detected between configurations or sources."""

    pass


class NestingTooDeepError(VPNAPIError):
    """Maximum allowed nesting depth exceeded."""

    pass


class TooManyConfigsError(VPNAPIError):
    """Exceeded the maximum number of configurations allowed."""

    pass


class TooManySourcesError(VPNAPIError):
    """Exceeded the maximum number of sources allowed."""

    pass


class TooManySubscriptionsError(VPNAPIError):
    """Exceeded the maximum number of subscriptions allowed."""

    pass


class ExternalFetchError(VPNAPIError):
    """Failed to fetch external resource (network, DNS, or HTTP error)."""

    pass


class CacheError(VPNAPIError):
    """Cache operation failed (read/write/invalid state)."""

    pass


# ═══════════════════════════════════════════════════════════════════════════
# Error Mapping
# ═══════════════════════════════════════════════════════════════════════════


_STATUS_CODE_MAP: dict[int, type[VPNAPIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
    500: ServerError,
    503: ServiceUnavailableError,
}


_ERROR_TYPE_MAP: dict[str, type[VPNAPIError]] = {
    "subscription_not_found": SubscriptionNotFoundError,
    "source_not_found": SourceNotFoundError,
    "invalid_url": InvalidURLError,
    "rate_limit_exceeded": RateLimitError,
}


def get_exception_for_status(
    status_code: int,
    message: str,
    response_data: dict[str, Any] | None = None,
) -> VPNAPIError:
    """
    Get appropriate exception for HTTP status code.

    Args:
        status_code: HTTP status code
        message: Error message
        response_data: Response data from API

    Returns:
        Appropriate exception instance
    """
    response_data = response_data or {}

    # Check for specific error types in response
    error_type = response_data.get("error", "")
    if error_type in _ERROR_TYPE_MAP:
        exception_class = _ERROR_TYPE_MAP[error_type]

        # Extract retry_after for rate limits
        retry_after = None
        if error_type == "rate_limit_exceeded":
            retry_after = response_data.get("retry_after")

        return exception_class(
            message=message,
            status_code=status_code,
            response_data=response_data,
            retry_after=retry_after,
        )

    # Fallback to status code mapping
    exception_class = _STATUS_CODE_MAP.get(status_code, VPNAPIError)
    return exception_class(
        message=message,
        status_code=status_code,
        response_data=response_data,
    )
