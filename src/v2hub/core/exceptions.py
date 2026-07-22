"""Custom exceptions for VPN Subscription API client.

Comprehensive exception hierarchy with error context and recovery hints.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "CacheError",
    "CircularReferenceError",
    "ConflictError",
    "DuplicateNameError",
    "ExternalFetchError",
    "InvalidConfigError",
    "InvalidURLError",
    "NestingTooDeepError",
    "NetworkError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ServiceUnavailableError",
    "SourceNotFoundError",
    "SubscriptionNotFoundError",
    "TimeoutError",
    "TooManyConfigsError",
    "TooManySourcesError",
    "TooManySubscriptionsError",
    "VPNAPIError",
    "ValidationError",
    "get_exception_for_error",
    "get_exception_for_exception",
    "get_exception_for_status",
]


class VPNAPIError(Exception):
    """Base exception for all VPN API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_data: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.retry_after = retry_after
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"[{self.status_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"retry_after={self.retry_after})"
        )

    @property
    def is_retryable(self) -> bool:
        return isinstance(
            self,
            (TimeoutError, ServerError, ServiceUnavailableError, RateLimitError, NetworkError),
        )

    @property
    def recovery_hint(self) -> str:
        hints = {
            ValidationError: "Check request parameters and fix validation errors",
            AuthenticationError: "Verify API token is valid and not expired",
            AuthorizationError: "Verify your account has permission for this operation",
            NotFoundError: "Ensure the resource exists and token/name is correct",
            ConflictError: "Resource already exists - use update or choose different name",
            RateLimitError: "Wait before retrying - rate limit exceeded",
            ServerError: "Temporary server error - retry after delay",
            ServiceUnavailableError: "Service temporarily unavailable - retry later",
            NetworkError: "Check network connectivity and retry",
            TimeoutError: "Request timed out - retry with longer timeout",
            InvalidURLError: "Fix the source URL; internal/local/private URLs are blocked",
            InvalidConfigError: "Validate config schema and unsupported fields",
            DuplicateNameError: "Choose a unique name or update the existing item",
            CircularReferenceError: "Remove the dependency cycle and try again",
            NestingTooDeepError: "Reduce nesting depth and retry",
            TooManySubscriptionsError: "Remove some subscriptions or increase the limit",
            TooManyConfigsError: "Remove some configs or increase the limit",
            TooManySourcesError: "Remove some sources or increase the limit",
            ExternalFetchError: "Check external URL, DNS, TLS, and remote server availability",
            CacheError: "Inspect cache backend health and permissions",
        }
        return hints.get(type(self), "Contact API support if problem persists")


class ValidationError(VPNAPIError):
    """Request validation failed (400/422)."""


class AuthenticationError(VPNAPIError):
    """Invalid or missing API token (401)."""


class AuthorizationError(VPNAPIError):
    """Insufficient permissions for the requested operation (403)."""


class NotFoundError(VPNAPIError):
    """Resource not found (404)."""


class ConflictError(VPNAPIError):
    """Resource already exists (409)."""


class RateLimitError(VPNAPIError):
    """Rate limit exceeded (429)."""

    @property
    def recovery_hint(self) -> str:
        if self.retry_after is not None:
            return f"Rate limited - wait {self.retry_after} seconds before retrying"
        return "Rate limited - wait before retrying"


class ServerError(VPNAPIError):
    """Internal server error (500)."""


class ServiceUnavailableError(VPNAPIError):
    """Service temporarily unavailable (503)."""


class NetworkError(VPNAPIError):
    """Network connection error."""


class TimeoutError(VPNAPIError):
    """Request timeout."""


class InvalidURLError(ValidationError):
    """Invalid URL provided (SSRF protection triggered)."""

    @property
    def recovery_hint(self) -> str:
        return "URL validation failed - ensure URL is publicly accessible and not internal/local"


class SubscriptionNotFoundError(NotFoundError):
    """Subscription not found by token or name."""

    @property
    def recovery_hint(self) -> str:
        return "Subscription not found - verify token/name or create new subscription"


class SourceNotFoundError(NotFoundError):
    """Source not found by ID."""

    @property
    def recovery_hint(self) -> str:
        return "Source not found - verify source ID exists in subscription"


class InvalidConfigError(VPNAPIError):
    """Invalid configuration format or unsupported structure."""


class DuplicateNameError(ConflictError):
    """Configuration with the same name already exists."""


class CircularReferenceError(VPNAPIError):
    """Circular dependency detected between configurations or sources."""


class NestingTooDeepError(VPNAPIError):
    """Maximum allowed nesting depth exceeded."""


class TooManyConfigsError(VPNAPIError):
    """Exceeded the maximum number of configurations allowed."""


class TooManySourcesError(VPNAPIError):
    """Exceeded the maximum number of sources allowed."""


class TooManySubscriptionsError(VPNAPIError):
    """Exceeded the maximum number of subscriptions allowed."""


class ExternalFetchError(VPNAPIError):
    """Failed to fetch external resource (network, DNS, or HTTP error)."""


class CacheError(VPNAPIError):
    """Cache operation failed (read/write/invalid state)."""


_STATUS_CODE_MAP: dict[int, type[VPNAPIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
    500: ServerError,
    502: ServiceUnavailableError,
    503: ServiceUnavailableError,
    504: TimeoutError,
}

_ERROR_TYPE_MAP: dict[str, type[VPNAPIError]] = {
    "validation_error": ValidationError,
    "authentication_error": AuthenticationError,
    "authorization_error": AuthorizationError,
    "permission_denied": AuthorizationError,
    "not_found": NotFoundError,
    "subscription_not_found": SubscriptionNotFoundError,
    "source_not_found": SourceNotFoundError,
    "conflict": ConflictError,
    "duplicate_name": DuplicateNameError,
    "rate_limit_exceeded": RateLimitError,
    "timeout": TimeoutError,
    "server_error": ServerError,
    "service_unavailable": ServiceUnavailableError,
    "invalid_url": InvalidURLError,
    "invalid_config": InvalidConfigError,
    "circular_reference": CircularReferenceError,
    "nesting_too_deep": NestingTooDeepError,
    "too_many_subscriptions": TooManySubscriptionsError,
    "too_many_configs": TooManyConfigsError,
    "too_many_sources": TooManySourcesError,
    "external_fetch_error": ExternalFetchError,
    "cache_error": CacheError,
    "network_error": NetworkError,
}


def _unwrap_response_data(response_data: dict[str, Any]) -> dict[str, Any]:
    detail = response_data.get("detail")
    if isinstance(detail, dict):
        return detail
    return response_data


def _normalize_error_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _extract_message(response_data: dict[str, Any], fallback: str) -> str:
    data = _unwrap_response_data(response_data)

    for key in ("message", "detail", "error_message", "description"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
        if isinstance(first, dict):
            for key in ("message", "detail", "error"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return fallback


def _extract_retry_after(response_data: dict[str, Any]) -> int | None:
    data = _unwrap_response_data(response_data)

    value = data.get("retry_after")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _extract_error_type(response_data: dict[str, Any]) -> str:
    data = _unwrap_response_data(response_data)

    for key in ("error", "error_code", "code", "type"):
        value = data.get(key)
        normalized = _normalize_error_key(value)
        if normalized:
            return normalized

    return ""


def _build_exception(
    exception_class: type[VPNAPIError],
    message: str,
    status_code: int | None,
    response_data: dict[str, Any],
    retry_after: int | None = None,
) -> VPNAPIError:
    return exception_class(
        message=message,
        status_code=status_code,
        response_data=response_data,
        retry_after=retry_after,
    )


def get_exception_for_status(
    status_code: int,
    message: str,
    response_data: dict[str, Any] | None = None,
) -> VPNAPIError:
    """Map HTTP status code to a typed exception."""
    response_data = response_data or {}
    retry_after = _extract_retry_after(response_data)
    message = _extract_message(response_data, message)

    error_type = _extract_error_type(response_data)
    if error_type in _ERROR_TYPE_MAP:
        exc_cls = _ERROR_TYPE_MAP[error_type]
        return _build_exception(exc_cls, message, status_code, response_data, retry_after)

    exc_cls = _STATUS_CODE_MAP.get(status_code, VPNAPIError)
    return _build_exception(exc_cls, message, status_code, response_data, retry_after)


def get_exception_for_error(
    message: str,
    response_data: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> VPNAPIError:
    """
    Map API payload without relying on status code.
    Useful when backend returns error objects with no HTTP status context.
    """
    response_data = response_data or {}
    retry_after = _extract_retry_after(response_data)
    message = _extract_message(response_data, message)

    error_type = _extract_error_type(response_data)
    if error_type in _ERROR_TYPE_MAP:
        exc_cls = _ERROR_TYPE_MAP[error_type]
        return _build_exception(exc_cls, message, status_code, response_data, retry_after)

    if status_code is not None:
        return get_exception_for_status(status_code, message, response_data)

    return VPNAPIError(message=message, response_data=response_data, retry_after=retry_after)


def get_exception_for_exception(exc: Exception, message: str | None = None) -> VPNAPIError:
    """
    Wrap transport/runtime exceptions into client exceptions.
    Useful for requests/httpx/aiohttp errors.
    """
    text = message or str(exc) or exc.__class__.__name__

    timeout_types = ("Timeout",)
    network_types = ("Connection", "Network", "DNS", "SSLError", "ProxyError")

    name = exc.__class__.__name__
    if any(part in name for part in timeout_types):
        return TimeoutError(message=text)
    if any(part in name for part in network_types):
        return NetworkError(message=text)

    return VPNAPIError(message=text)
