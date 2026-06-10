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

__version__ = "1.0.3"
__author__ = "nestt"
__api_version__ = "v1"
__all__ = [
    # Version
    "__version__",
    "__api_version__",
    # Clients
    "AsyncVPNClient",
    "VPNClient",
    # Models
    "Subscription",
    "SubscriptionListItem",
    "Source",
    "SourceType",
    "RefreshSubscriptionResponse",
    "PublicSubscriptionResponse",
    "ErrorResponse",
    # Request models
    "SubscriptionCreateRequest",
    "SubscriptionUpdateRequest",
    "SourceAddRequest",
    "SourceReplaceRequest",
    "SourceRemoveRequest",
    "CommentUpdateRequest",
    # Exceptions
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
    # Retry
    "RetryConfig",
    "CircuitBreakerConfig",
    "CircuitState",
]

# Import clients
from .async_client import AsyncVPNClient
from .client import VPNClient

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

# Import exceptions
from .core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InvalidURLError,
    InvalidConfigError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    SourceNotFoundError,
    DuplicateNameError,
    CircularReferenceError,
    NestingTooDeepError,
    TooManyConfigsError,
    TooManySourcesError,
    TooManySubscriptionsError,
    ExternalFetchError,
    CacheError,
    SubscriptionNotFoundError,
    TimeoutError,
    ValidationError,
    VPNAPIError,
)

# Import retry utilities
from .core.retry import CircuitBreakerConfig, CircuitState, RetryConfig
