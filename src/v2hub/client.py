"""
Synchronous VPN Subscription API client.

Sync wrapper with proper event loop management.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypeVar

import typing_extensions

from v2hub.async_client import AsyncVPNClient

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from v2hub.core.retry import CircuitBreakerConfig, RetryConfig
    from v2hub.models import (
        ProviderConnectionDeleteResponse,
        ProviderConnectionResponse,
        PublicSubscriptionResponse,
        RefreshSubscriptionResponse,
        SourceCreate,
        Subscription,
        SubscriptionListItem,
    )

__all__ = ["VPNClient"]

T = TypeVar("T")

# ═══════════════════════════════════════════════════════════════════════════
# Sync VPN Client
# ═══════════════════════════════════════════════════════════════════════════


class VPNClient:
    """
    Synchronous VPN Subscription API client.

    Thread-safe sync wrapper around AsyncVPNClient for non-async code.
    Uses proper event loop management for compatibility.

    Features:
    - All API endpoints
    - Automatic retries with exponential backoff
    - Circuit breaker for resilience
    - Pydantic models for validation
    - Type hints for IDE autocomplete

    Every subscription/source method accepts an optional, keyword-only
    `as_provider_for_user_id` argument:
    - omitted (None, the default) -> normal self-service call, for the
      account that owns `api_token`.
    - provided -> `api_token` acts as a PROVIDER managing subscriptions
      on behalf of the end-user whose ID is given (requires `api_token`
      to belong to a provider account).

    The parameter is intentionally verbose and keyword-only so it can't
    be passed positionally or confused with some other ID — passing it
    always means "act as a provider for this specific end-user".

    Example (self-service):
        with VPNClient("https://api.example.com", "token") as client:
            sub = client.create_subscription("my-vpn")
            client.add_sources(sub.token, ["vless://..."])
            sub = client.get_subscription(sub.token)

    Example (provider managing multiple end-users with one client):
        with VPNClient("https://api.example.com", "provider-token") as client:
            sub1 = client.create_subscription("vpn", as_provider_for_user_id="user-123")
            sub2 = client.create_subscription("vpn", as_provider_for_user_id="user-456")
            client.add_sources(
                sub1.token, ["vless://..."], as_provider_for_user_id="user-123"
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
        Initialize sync VPN API client.

        Args:
            base_url: API base URL (e.g., "https://api.example.com")
            api_token: API authentication token
            timeout: Request timeout in seconds
            retry_config: Custom retry configuration
            circuit_breaker_config: Circuit breaker configuration
        """
        self._async_client: AsyncVPNClient = AsyncVPNClient(
            base_url=base_url,
            api_token=api_token,
            timeout=timeout,
            retry_config=retry_config,
            circuit_breaker_config=circuit_breaker_config,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._owned_loop = False

    def __enter__(self) -> VPNClient:
        """Context manager entry."""
        self._loop = asyncio.new_event_loop()
        self._owned_loop = True
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_client.connect())
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._loop and self._owned_loop:
            self._loop.run_until_complete(self._async_client.close())
            self._loop.close()
            self._loop = None
            self._owned_loop = False

    def _run(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Run async coroutine synchronously.

        Args:
            coro: Coroutine to run

        Returns:
            Coroutine result
        """
        if self._loop is not None and self._owned_loop:
            return self._loop.run_until_complete(coro)
        # If not in context manager, create temporary loop
        return asyncio.run(coro)

    # ═══════════════════════════════════════════════════════════════════════
    # Subscription Management
    # ═══════════════════════════════════════════════════════════════════════

    def list_subscriptions(
        self, *, as_provider_for_user_id: int | None = None
    ) -> list[SubscriptionListItem]:
        """
        List all subscriptions.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset for
                normal self-service (lists the caller's own subscriptions).
                Set to an end-user's ID to instead list that end-user's
                subscriptions, acting as a provider on their behalf.
        """
        return self._run(
            self._async_client.list_subscriptions(as_provider_for_user_id=as_provider_for_user_id)
        )

    def create_subscription(
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
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                create the subscription for the caller's own account.
                Set to an end-user's ID to instead create it on that
                end-user's behalf, acting as a provider.
        """
        return self._run(
            self._async_client.create_subscription(
                name,
                description,
                sources,
                as_provider_for_user_id=as_provider_for_user_id,
            )
        )

    def get_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> Subscription:
        """
        Get subscription by token.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset for
                normal self-service lookup. Set to an end-user's ID to
                look up their subscription as a provider on their behalf.
        """
        return self._run(
            self._async_client.get_subscription(
                token, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    def update_subscription(
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
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                update the caller's own subscription. Set to an end-user's
                ID to update their subscription as a provider on their behalf.
        """
        return self._run(
            self._async_client.update_subscription(
                token,
                name,
                description,
                as_provider_for_user_id=as_provider_for_user_id,
            )
        )

    def delete_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> None:
        """
        Delete subscription.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to
                delete the caller's own subscription. Set to an end-user's
                ID to delete their subscription as a provider on their behalf.
        """
        return self._run(
            self._async_client.delete_subscription(
                token, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Source Management
    # ═══════════════════════════════════════════════════════════════════════

    def add_sources(
        self,
        token: str,
        sources: list[SourceCreate],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Add sources to subscription.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        return self._run(
            self._async_client.add_sources(
                token, sources, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    def replace_sources(
        self,
        token: str,
        sources: list[SourceCreate],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Replace all sources in subscription.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        return self._run(
            self._async_client.replace_sources(
                token, sources, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    def remove_sources(
        self,
        token: str,
        source_ids: list[str],
        *,
        as_provider_for_user_id: int | None = None,
    ) -> Subscription:
        """
        Remove specific sources from subscription.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        return self._run(
            self._async_client.remove_sources(
                token, source_ids, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    @typing_extensions.deprecated(
        "The `update_comment()` method is deprecated; use `update_source()` instead.", category=None
    )
    def update_comment(
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
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        self._run(
            self._async_client.update_comment(
                token,
                config_id,
                comment,
                as_provider_for_user_id=as_provider_for_user_id,
            )
        )

    def update_source(
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

        Only fields explicitly passed (non-None) are changed; any field
        left as None is left untouched server-side.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        self._run(
            self._async_client.update_source(
                token=token,
                config_id=config_id,
                comment=comment,
                is_hidden=is_hidden,
                max_depth=max_depth,
                as_provider_for_user_id=as_provider_for_user_id,
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Operations
    # ═══════════════════════════════════════════════════════════════════════

    def refresh_subscription(
        self, token: str, *, as_provider_for_user_id: int | None = None
    ) -> RefreshSubscriptionResponse:
        """
        Manually refresh external URL sources.

        Args:
            as_provider_for_user_id: PROVIDER USE ONLY. Leave unset to act
                on the caller's own subscription. Set to an end-user's ID
                to act as a provider on their behalf.
        """
        return self._run(
            self._async_client.refresh_subscription(
                token, as_provider_for_user_id=as_provider_for_user_id
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Provider Connection Management
    # ═══════════════════════════════════════════════════════════════════════
    #
    # These manage the authorization link between a provider and an
    # end-user — separate from, and a prerequisite for, the
    # `as_provider_for_user_id=` subscription/source calls above.
    # `api_token` must belong to a provider account for all of these.

    def get_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """Get the current authorization status between this provider and a user."""
        return self._run(self._async_client.get_provider_connection(user_id))

    def create_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """
        Create (or re-request) an authorization connection to a user.

        Once approved, this provider can manage the user's subscriptions
        via the `as_provider_for_user_id=user_id` argument on subscription
        and source methods.
        """
        return self._run(self._async_client.create_provider_connection(user_id))

    def revoke_provider_connection(self, user_id: int) -> ProviderConnectionResponse:
        """Revoke this provider's authorization for a user (without deleting the record)."""
        return self._run(self._async_client.revoke_provider_connection(user_id))

    def delete_provider_connection(self, user_id: int) -> ProviderConnectionDeleteResponse:
        """Permanently remove the authorization connection record to a user."""
        return self._run(self._async_client.delete_provider_connection(user_id))

    # ═══════════════════════════════════════════════════════════════════════
    # Public Endpoints
    # ═══════════════════════════════════════════════════════════════════════

    def get_public_subscription(self, token: str) -> PublicSubscriptionResponse:
        """Get public subscription configs (base64 encoded)."""
        return self._run(self._async_client.get_public_subscription(token))
