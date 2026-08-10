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

from v2hub import __api_version__
from v2hub.core.exceptions import ValidationError, VPNAPIError
from v2hub.core.retry import CircuitBreaker, CircuitBreakerConfig, RetryConfig, with_async_retry
from v2hub.http.client import HTTPClient
from v2hub.models import (
    CommentUpdateRequest,
    ProviderConnectionDeleteResponse,
    ProviderConnectionResponse,
    PublicSubscriptionResponse,
    RefreshSubscriptionResponse,
    SourceAddRequest,
    SourceCreate,
    SourceRemoveRequest,
    SourceReplaceRequest,
    SourceUpdateRequest,
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

    Every subscription/source method accepts an optional, keyword-only
    `as_provider_for_user_id` argument:
    - omitted (None, the default) -> normal self-service call, for the
      account that owns `api_token`. Hits ``/api/{version}/subs/...``.
    - provided -> `api_token` acts as a PROVIDER managing subscriptions
      on behalf of the end-user whose ID is given. Hits
      ``/api/{version}/providers/{as_provider_for_user_id}/subs/...`` and
      requires `api_token` to belong to a provider account.

    The parameter is intentionally verbose and keyword-only (not just
    `user_id`) so it can't be passed positionally or confused with some
    other ID by a developer skimming the call — passing it always means
    "act as a provider for this specific end-user", never "the current
    user" or anything else.

    A single client instance/connection is enough to act both as a normal
    self-service user and as a provider managing any number of end-users —
    just pass `as_provider_for_user_id` on the calls that need it.

    Note: a provider must first have an APPROVED connection to a given
    user_id (see the "Provider Connection Management" methods below,
    e.g. `create_provider_connection()`) before any
    `as_provider_for_user_id=` subscription call for that user_id will
    succeed.

    Example (self-service — the common case, nothing provider-related):
        async with AsyncVPNClient("https://api.example.com", "token") as client:
            sub = await client.create_subscription("my-vpn")
            await client.add_sources(sub.token, ["vless://..."])

    Example (provider managing multiple end-users with one client):
        async with AsyncVPNClient("https://api.example.com", "provider-token") as client:
            await client.create_provider_connection(123)  # establish authorization first
            sub1 = await client.create_subscription("vpn", as_provider_for_user_id=123)
            sub2 = await client.create_subscription("vpn", as_provider_for_user_id=456)
            await client.add_sources(
                sub1.token, ["vless://..."], as_provider_for_user_id=123
            )
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
    def _subs_path(as_provider_for_user_id: int | None) -> str:
        """
        Base path for subscription endpoints.

        Args:
            as_provider_for_user_id: None for the self-service path
                (``/subs``). Otherwise, the end-user ID to manage as a
                provider, giving the provider-scoped path
                (``/providers/{id}/subs``).
        """
        if as_provider_for_user_id is not None:
            return f"/api/{__api_version__}/providers/{as_provider_for_user_id}/subs"
        return f"/api/{__api_version__}/subs"

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
    async def list_subscriptions(
        self, *, as_provider_for_user_id: int | None = None
    ) -> list[SubscriptionListItem]:
        """
        List all subscriptions.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset for
                normal self-service (lists the caller's own subscriptions).
                Set to an end-user's numeric user_id to instead list that end-user's
                subscriptions, acting as a provider on their behalf
                (requires a provider API token).

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
        response = await self._http_client.get(self._subs_path(as_provider_for_user_id))
        data = response.json()
        return [SubscriptionListItem(**item) for item in data]

    @with_async_retry()
    async def create_subscription(
        self,
        name: str,
        description: str | None = None,
        sources: list[SourceCreate] | None = None,
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Create a new subscription.

        Args:
            name: Subscription name (1-64 chars)
            description: Optional description (max 255 chars)
            sources: Optional initial sources
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                create the subscription for the caller's own account.
                Set to an end-user's numeric user_id to instead create it on that
                end-user's behalf, acting as a provider (requires a
                provider API token).

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
            self._subs_path(as_provider_for_user_id),
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def get_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> Subscription:
        """
        Get subscription by token.

        Args:
            token: Subscription token
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset for
                normal self-service lookup. Set to an end-user's numeric user_id to
                look up their subscription as a provider on their behalf.

        Returns:
            Subscription details

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        response = await self._http_client.get(
            f"{self._subs_path(as_provider_for_user_id)}/{token}"
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def update_subscription(
        self,
        token: str,
        name: str | None = None,
        description: str | None = None,
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Update subscription metadata.

        Args:
            token: Subscription token
            name: New name (optional)
            description: New description (optional)
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                update the caller's own subscription. Set to an end-user's
                ID to update their subscription as a provider on their behalf.

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
            f"{self._subs_path(as_provider_for_user_id)}/{token}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def delete_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> None:
        """
        Delete subscription.

        Args:
            token: Subscription token
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                delete the caller's own subscription. Set to an end-user's
                ID to delete their subscription as a provider on their behalf.

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        await self._http_client.delete(f"{self._subs_path(as_provider_for_user_id)}/{token}")

    # ═══════════════════════════════════════════════════════════════════════
    # Source Management
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def add_sources(
        self,
        token: str,
        sources: list[SourceCreate],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Add sources to subscription.

        Args:
            token: Subscription token
            sources: List of sources to add (configs or URLs)
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

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
            f"{self._subs_path(as_provider_for_user_id)}/{token}/sources",
            json=request.model_dump(mode="json"),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def replace_sources(
        self,
        token: str,
        sources: list[SourceCreate],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Replace all sources in subscription.

        Args:
            token: Subscription token
            sources: New list of sources (replaces all existing)
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

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
            f"{self._subs_path(as_provider_for_user_id)}/{token}/sources",
            json=request.model_dump(mode="json"),
        )
        return Subscription(**response.json())

    @with_async_retry()
    async def remove_sources(
        self,
        token: str,
        source_ids: list[str],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Remove specific sources from subscription.

        Args:
            token: Subscription token
            source_ids: List of source IDs to remove
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

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
            f"{self._subs_path(as_provider_for_user_id)}/{token}/sources",
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
        *,
        as_provider_for_user_id: int | None = None,
    ) -> None:
        """
        Update comment for a specific config.

        Deprecated: use `update_source()` instead.

        Args:
            token: Subscription token
            config_id: Config id
            comment: Comment text (None to remove)
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

        Raises:
            SubscriptionNotFoundError: Subscription not found
            ValidationError: Invalid parameters
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        request = self._build_request(CommentUpdateRequest, config_id=config_id, comment=comment)
        await self._http_client.patch(
            f"{self._subs_path(as_provider_for_user_id)}/{token}/comments",
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
        *,
        as_provider_for_user_id: int | None = None,
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
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

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
            f"{self._subs_path(as_provider_for_user_id)}/{token}/config",
            json=request.model_dump(mode="json", exclude_none=True),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Operations
    # ═══════════════════════════════════════════════════════════════════════

    @with_async_retry()
    async def refresh_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> RefreshSubscriptionResponse:
        """
        Manually refresh external URL sources.

        Args:
            token: Subscription token
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's numeric user_id
                to act as a provider on their behalf.

        Returns:
            Refresh result with statistics

        Raises:
            SubscriptionNotFoundError: Subscription not found
            AuthenticationError: Invalid API token
            VPNAPIError: Other API errors
        """
        response = await self._http_client.post(
            f"{self._subs_path(as_provider_for_user_id)}/{token}/refresh"
        )
        return RefreshSubscriptionResponse(**response.json())

    # ═══════════════════════════════════════════════════════════════════════
    # Provider Connection Management
    # ═══════════════════════════════════════════════════════════════════════
    #
    # These manage the authorization link between a provider and an
    # end-user (approve/check/revoke/delete access) — separate from, and a
    # prerequisite for, the `as_provider_for_user_id=` subscription/source
    # calls above. Until a connection exists and is APPROVED for a given
    # user_id, provider-mode subscription calls for that user_id will fail
    # server-side (403/404), regardless of how they're called here.
    #
    # `api_token` must belong to a provider account for all of these.

    @with_async_retry()
    async def get_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """
        Get the current authorization status between this provider and a user.

        Args:
            user_id: The end-user's numeric ID.

        Returns:
            Current connection status (e.g. pending/approved/revoked).

        Raises:
            AuthenticationError: Invalid API token, or user not found.
            VPNAPIError: Other API errors.
        """
        response = await self._http_client.get(f"/api/{__api_version__}/providers/{user_id}")
        return ProviderConnectionResponse(**response.json())

    @with_async_retry()
    async def create_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """
        Create (or re-request) an authorization connection to a user.

        Currently auto-approves rather than waiting on user confirmation —
        see the server's own docs/changelog for the current behavior, since
        this is documented server-side as a temporary/evolving flow. Once
        approved, this provider can manage the user's subscriptions via the
        `as_provider_for_user_id=user_id` argument on subscription/source
        methods.

        Args:
            user_id: The end-user's numeric ID. If no account exists yet
                for this ID, one is created.

        Returns:
            The resulting connection status.

        Raises:
            TooManyApprovedUsersError: Provider's approved-user quota reached.
            AuthenticationError: Invalid API token.
            VPNAPIError: Other API errors.
        """
        response = await self._http_client.post(f"/api/{__api_version__}/providers/{user_id}")
        return ProviderConnectionResponse(**response.json())

    @with_async_retry()
    async def revoke_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """
        Revoke this provider's authorization for a user, without deleting
        the connection record. A revoked connection can be re-approved by
        calling `create_provider_connection()` again.

        Args:
            user_id: The end-user's numeric ID.

        Returns:
            The resulting connection status (REVOKED).

        Raises:
            AuthenticationError: No existing authorization to revoke.
            VPNAPIError: Other API errors.
        """
        response = await self._http_client.post(
            f"/api/{__api_version__}/providers/{user_id}/revoke"
        )
        return ProviderConnectionResponse(**response.json())

    @with_async_retry()
    async def delete_provider_connection(self, user_id: int) -> ProviderConnectionDeleteResponse:
        """
        Permanently remove the authorization connection record to a user.

        Unlike `revoke_provider_connection()`, this deletes the record
        entirely rather than just marking it revoked.

        Args:
            user_id: The end-user's numeric ID.

        Returns:
            Confirmation of deletion.

        Raises:
            AuthenticationError: Invalid API token.
            VPNAPIError: Other API errors.
        """
        response = await self._http_client.delete(f"/api/{__api_version__}/providers/{user_id}")
        return ProviderConnectionDeleteResponse(**response.json())

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
