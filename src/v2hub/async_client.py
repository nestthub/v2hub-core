"""
Asynchronous VPN Subscription API client.

Production-grade async client with comprehensive features.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, TypeVar

import typing_extensions
from pydantic import ValidationError as PydanticValidationError

from v2hub.core.exceptions import ValidationError, VPNAPIError
from v2hub.models.requests import SourceCreate, SourceUpdateRequest

from . import __api_version__
from .core.retry import CircuitBreaker, CircuitBreakerConfig, RetryConfig, with_async_retry
from .http.client import HTTPClient
from .models import (
    CommentUpdateRequest,
    PublicSubscriptionResponse,
    RefreshSubscriptionResponse,
    SourceAddRequest,
    SourceRemoveRequest,
    SourceReplaceRequest,
    Subscription,
    SubscriptionCreateRequest,
    SubscriptionListItem,
    SubscriptionUpdateRequest,
)

logger = logging.getLogger(__name__)

__all__ = ["AsyncVPNClient"]

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════
# Async VPN Client
# ═══════════════════════════════════════════════════════════════════════════


class AsyncVPNClient:
    """
    Asynchronous VPN Subscription API client.

    Production-grade features:
    - Full async/await support
    - Automatic retries with exponential backoff
    - Circuit breaker for resilience
    - Pydantic models with validation
    - Comprehensive error handling
    - Request/response logging

    Example:
        async with AsyncVPNClient("https://api.example.com", "token") as client:
            # Create subscription
            sub = await client.create_subscription("my-vpn")

            # Add sources
            await client.add_sources(sub.token, ["vless://..."])

            # Get subscription
            sub = await client.get_subscription(sub.token)
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = 30.0,
        retry_config: RetryConfig | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """
        Initialize async VPN API client.

        Args:
            base_url: API base URL (e.g., "https://api.example.com")
            api_token: API authentication token
            timeout: Request timeout in seconds
            retry_config: Custom retry configuration
            circuit_breaker_config: Circuit breaker configuration
        """
        self.base_url = base_url
        self.api_token = api_token
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()

        # Initialize HTTP client
        self._http_client = HTTPClient(
            base_url=base_url,
            headers={
                "API-Token": api_token,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(self.circuit_breaker_config)

    @staticmethod
    def _build_request(model_cls: type[T], /, **kwargs: Any) -> T:
        """
        Construct a pydantic request model, mapping validation errors to v2hub.ValidationError.

        This ensures callers only ever need to catch v2hub's own exception hierarchy
        (ValidationError / VPNAPIError) instead of also needing to know about and
        catch pydantic's ValidationError, which would leak an implementation detail.
        """
        try:
            return model_cls(**kwargs)
        except PydanticValidationError as e:
            raise ValidationError(str(e)) from e

    async def __aenter__(self) -> AsyncVPNClient:
        """Async context manager entry."""
        await self._http_client.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._http_client.close()

    async def connect(self) -> None:
        """Initialize HTTP client connection."""
        await self._http_client.connect()

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self._http_client.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Subscription Management
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def list_subscriptions(self) -> list[SubscriptionListItem]:
        """
        List all subscriptions.

        Returns:
            List of subscriptions

        Raises:
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors

        Example:
            subs = await client.list_subscriptions()
            for sub in subs:
                print(f"{sub.name}: {sub.sources_count} configs")
        """
        response = await self._http_client.get(f"/api/{__api_version__}/subs")
        data = response.json()
        return [SubscriptionListItem(**item) for item in data]

    @with_async_retry()
    async def create_subscription(
        self,
        name: str,
        description: str | None = None,
        sources: list[SourceCreate] | None = None,
    ) -> Subscription:
        """
        Create a new subscription.

        Args:
            name: Subscription name (1-64 chars)
            description: Optional description (max 255 chars)
            sources: Optional initial sources

        Returns:
            Created subscription

        Raises:
            ValidationError: Invalid parameters
            ConflictError: Subscription name already exists
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors

        Example:
            sub = await client.create_subscription(
                "my-vpn",
                description="Production VPN configs",
                sources=["vless://uuid@server:443#Server1"]
            )
        """
        if sources is None:
            sources = []

        request = self._build_request(
            SubscriptionCreateRequest,
            name=name,
            description=description,
            sources=sources,
        )
        response = await self._http_client.post(
            f"/api/{__api_version__}/subs",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def get_subscription(self, token: str) -> Subscription:
        """
        Get subscription by token.

        Args:
            token: Subscription token

        Returns:
            Subscription details

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        response = await self._http_client.get(f"/api/{__api_version__}/subs/{token}")
        return Subscription(**response.json())

    @with_async_retry()
    async def get_subscription_by_name(self, name: str) -> Subscription:
        """
        Get subscription by name.

        Args:
            name: Subscription name

        Returns:
            Subscription details

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        response = await self._http_client.get(f"/api/{__api_version__}/subs/by-name/{name}")
        return Subscription(**response.json())

    @with_async_retry()
    async def update_subscription(
        self,
        token: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Subscription:
        """
        Update subscription metadata.

        Args:
            token: Subscription token
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: Subscription not found
            ValidationError: Invalid parameters
            ConflictError: New name already exists
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(SubscriptionUpdateRequest, name=name, description=description)
        response = await self._http_client.patch(
            f"/api/{__api_version__}/subs/{token}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def delete_subscription(self, token: str) -> None:
        """
        Delete subscription.

        Args:
            token: Subscription token

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        await self._http_client.delete(f"/api/{__api_version__}/subs/{token}")

    # ═══════════════════════════════════════════════════════════════════════
    # Source Management
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def add_sources(
        self,
        token: str,
        sources: list[SourceCreate],
    ) -> Subscription:
        """
        Add sources to subscription.

        Args:
            token: Subscription token
            sources: List of sources to add (configs or URLs)

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: Subscription not found
            ValidationError: Invalid sources
            InvalidURLError: Invalid URL (SSRF protection)
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(SourceAddRequest, sources=sources)
        response = await self._http_client.post(
            f"/api/{__api_version__}/subs/{token}/sources",
            json=request.model_dump(mode="json"),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def replace_sources(
        self,
        token: str,
        sources: list[SourceCreate],
    ) -> Subscription:
        """
        Replace all sources in subscription.

        Args:
            token: Subscription token
            sources: New list of sources (replaces all existing)

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: Subscription not found
            ValidationError: Invalid sources
            InvalidURLError: Invalid URL (SSRF protection)
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(SourceReplaceRequest, sources=sources)
        response = await self._http_client.put(
            f"/api/{__api_version__}/subs/{token}/sources",
            json=request.model_dump(mode="json"),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def remove_sources(
        self,
        token: str,
        source_ids: list[str],
    ) -> Subscription:
        """
        Remove specific sources from subscription.

        Args:
            token: Subscription token
            source_ids: List of source IDs to remove

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: Subscription not found
            SourceNotFoundError: Source ID not found
            ValidationError: Invalid parameters
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(SourceRemoveRequest, source_ids=source_ids)
        response = await self._http_client.request(
            "DELETE",
            f"/api/{__api_version__}/subs/{token}/sources",
            json=request.model_dump(mode="json"),
        )
        return Subscription(**response.json())

    @typing_extensions.deprecated(
        "The `update_comment()` method is deprecated; use `update_source()` instead.", category=None
    )
    @with_async_retry()
    async def update_comment(
        self,
        token: str,
        config_id: str,
        comment: str | None,
    ) -> None:
        """
        Update comment for a specific config.

        Args:
            token: Subscription token
            config_id: Config id
            comment: Comment text (None to remove)

        Returns:
            Updated subscription

        Raises:
            SubscriptionNotFoundError: Subscription not found
            ValidationError: Invalid parameters
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(CommentUpdateRequest, config_id=config_id, comment=comment)
        await self._http_client.patch(
            f"/api/{__api_version__}/subs/{token}/comments",
            json=request.model_dump(mode="json", exclude_none=True),
        )

    @with_async_retry()
    async def update_source(
        self,
        token: str,
        config_id: str,
        comment: str | None = None,
        is_hidden: bool | None = None,
        max_depth: int | None = None,
    ) -> None:
        """
        Partially update a source's settings within a subscription.

        Only fields explicitly passed (non-None) are changed server-side;
        any field left as None is left untouched. This means you don't
        need to know or re-supply a source's current is_hidden/max_depth
        just to change its comment, and vice versa.

        Args:
            token: Subscription token.
            config_id: Source configuration identifier.
            comment: New comment text, or None to leave unchanged.
            is_hidden: New hidden state, or None to leave unchanged.
            max_depth: New max nesting depth (0-3), or None to leave unchanged.

        Returns:
            Updated subscription.

        Raises:
            SubscriptionNotFoundError: Subscription not found.
            ValidationError: Invalid request parameters.
            AuthenticationError: Invalid API token.
            VPNAPIError: Other API errors.

        Example:
            # Only change is_hidden, leave comment and max_depth as they are
            await client.update_source(sub.token, "cfg123", is_hidden=True)
        """
        request = self._build_request(
            SourceUpdateRequest,
            config_id=config_id,
            comment=comment,
            is_hidden=is_hidden,
            max_depth=max_depth,
        )
        await self._http_client.patch(
            f"/api/{__api_version__}/subs/{token}/config",
            json=request.model_dump(mode="json", exclude_none=True),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Operations
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def refresh_subscription(self, token: str) -> RefreshSubscriptionResponse:
        """
        Manually refresh external URL sources.

        Args:
            token: Subscription token

        Returns:
            Refresh result with statistics

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        response = await self._http_client.post(f"/api/{__api_version__}/subs/{token}/refresh")
        return RefreshSubscriptionResponse(**response.json())

    # ═══════════════════════════════════════════════════════════════════════
    # Public Endpoints (No Auth Required)
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def get_public_subscription(self, token: str) -> PublicSubscriptionResponse:
        response = await self._http_client.get(f"/sub/{token}")

        if response.status_code != 200:
            raise VPNAPIError(f"HTTP {response.status_code}: {response.text}")

        # --- content (оставляем как есть, base64) ---
        content_b64 = response.text.strip()

        # --- title (декодируем, потому что модель хранит уже нормальную строку) ---
        title = "v2hub"
        title_header = response.headers.get("profile-title")

        if title_header and title_header.startswith("base64:"):
            try:
                encoded = title_header.split("base64:")[1]
                title = base64.b64decode(encoded).decode("utf-8")
            except Exception:
                # fallback — не валим всё из-за кривого заголовка
                pass

        return PublicSubscriptionResponse(
            title=title,
            content=content_b64,
        )
