"""
VPN Subscription API Client Library.

Professional Python client for VPN Subscription API with:
- Async and sync clients
- Pydantic models with validation
- Automatic retry logic with circuit breaker
- Comprehensive error handling
- Full type hints and IDE support
- Production-ready logging and observability

Example (Async):
    >>> async with AsyncVPNClient("https://api.example.com", "token") as client:
    ...     sub = await client.create_subscription("my-vpn")
    ...     await client.add_sources(sub.token, ["vless://..."])

Example (Sync):
    >>> with VPNClient("https://api.example.com", "token") as client:
    ...     sub = client.create_subscription("my-vpn")
    ...     client.add_sources(sub.token, ["vless://..."])
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, metadata, version

try:
    __version__ = version("v2hub")
    __author__ = metadata("v2hub")["Author-email"]
except PackageNotFoundError:
    __version__ = "unknown"
    __author__ = "unknown"

__api_version__ = "v1"
__all__ = [
    "AsyncVPNClient",
    "AuthenticationError",
    "AuthorizationError",
    "CacheError",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircularReferenceError",
    "CommentUpdateRequest",
    "ConflictError",
    "DuplicateNameError",
    "ErrorResponse",
    "ExternalFetchError",
    "InvalidConfigError",
    "InvalidURLError",
    "NestingTooDeepError",
    "NetworkError",
    "NotFoundError",
    "PublicSubscriptionResponse",
    "RateLimitError",
    "RefreshSubscriptionResponse",
    "RetryConfig",
    "ServerError",
    "ServiceUnavailableError",
    "Source",
    "SourceAddRequest",
    "SourceNotFoundError",
    "SourceRemoveRequest",
    "SourceReplaceRequest",
    "SourceType",
    "Subscription",
    "SubscriptionCreateRequest",
    "SubscriptionListItem",
    "SubscriptionNotFoundError",
    "SubscriptionUpdateRequest",
    "TimeoutError",
    "TooManyConfigsError",
    "TooManySourcesError",
    "TooManySubscriptionsError",
    "VPNAPIError",
    "VPNClient",
    "ValidationError",
    "__api_version__",
    "__version__",
]

# Import clients
from .async_client import AsyncVPNClient
from .client import VPNClient

# Import exceptions
from .core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    CircularReferenceError,
    ConflictError,
    DuplicateNameError,
    ExternalFetchError,
    InvalidConfigError,
    InvalidURLError,
    NestingTooDeepError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    SourceNotFoundError,
    SubscriptionNotFoundError,
    TimeoutError,
    TooManyConfigsError,
    TooManySourcesError,
    TooManySubscriptionsError,
    ValidationError,
    VPNAPIError,
)

# Import retry utilities
from .core.retry import CircuitBreakerConfig, CircuitState, RetryConfig

# Import models
from .models import (
    CommentUpdateRequest,
    ErrorResponse,
    PublicSubscriptionResponse,
    RefreshSubscriptionResponse,
    Source,
    SourceAddRequest,
    SourceRemoveRequest,
    SourceReplaceRequest,
    SourceType,
    Subscription,
    SubscriptionCreateRequest,
    SubscriptionListItem,
    SubscriptionUpdateRequest,
)
