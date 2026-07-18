"""
Synchronous VPN Subscription API client.

Sync wrapper with proper event loop management.
"""

from __future__ import annotations

import asyncio
from typing import Any
import typing_extensions

from v2hub.models.requests import SourceCreate

from .async_client import AsyncVPNClient
from .core.retry import CircuitBreakerConfig, RetryConfig
from .models import (
    PublicSubscriptionResponse,
    RefreshSubscriptionResponse,
    Subscription,
    SubscriptionListItem,
)

__all__ = ["VPNClient"]


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

    Example:
        with VPNClient("https://api.example.com", "token") as client:
            # Create subscription
            sub = client.create_subscription("my-vpn")

            # Add sources
            client.add_sources(sub.token, ["vless://..."])

            # Get subscription
            sub = client.get_subscription(sub.token)
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
        self._async_client = AsyncVPNClient(
            base_url=base_url,
            api_token=api_token,
            timeout=timeout,
            retry_config=retry_config,
            circuit_breaker_config=circuit_breaker_config,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._owned_loop = False

    def __enter__(self) -> "VPNClient":
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

    def _run(self, coro: Any) -> Any:
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

    def list_subscriptions(self) -> list[SubscriptionListItem]:
        """List all subscriptions."""
        return self._run(self._async_client.list_subscriptions())

    def create_subscription(
        self,
        name: str,
        description: str | None = None,
        sources: list[SourceCreate] | None = None,
    ) -> Subscription:
        """Create a new subscription."""
        return self._run(
            self._async_client.create_subscription(name, description, sources)
        )

    def get_subscription(self, token: str) -> Subscription:
        """Get subscription by token."""
        return self._run(self._async_client.get_subscription(token))

    def get_subscription_by_name(self, name: str) -> Subscription:
        """Get subscription by name."""
        return self._run(self._async_client.get_subscription_by_name(name))

    def update_subscription(
        self,
        token: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Subscription:
        """Update subscription metadata."""
        return self._run(
            self._async_client.update_subscription(token, name, description)
        )

    def delete_subscription(self, token: str) -> None:
        """Delete subscription."""
        return self._run(self._async_client.delete_subscription(token))

    # ═══════════════════════════════════════════════════════════════════════
    # Source Management
    # ═══════════════════════════════════════════════════════════════════════

    def add_sources(self, token: str, sources: list[SourceCreate]) -> Subscription:
        """Add sources to subscription."""
        return self._run(self._async_client.add_sources(token, sources))

    def replace_sources(self, token: str, sources: list[SourceCreate]) -> Subscription:
        """Replace all sources in subscription."""
        return self._run(self._async_client.replace_sources(token, sources))

    def remove_sources(self, token: str, source_ids: list[str]) -> Subscription:
        """Remove specific sources from subscription."""
        return self._run(self._async_client.remove_sources(token, source_ids))


    @typing_extensions.deprecated('The `update_comment()` method is deprecated; use `update_source()` instead.', category=None)
    def update_comment(
        self,
        token: str,
        config_id: str,
        comment: str | None,
    ):
        """Update comment for a specific config."""
        return self._run(
            self._async_client.update_comment(token, config_id, comment)
        )

    def update_source(
        self,
        token: str,
        config_id: str,
        comment: str | None = None,
        is_hidden: bool | None = None,
        max_depth: int | None = None,
    ):
        """
        Partially update a source's settings within a subscription.

        Only fields explicitly passed (non-None) are changed; any field
        left as None is left untouched server-side.
        """
        return self._run(
            self._async_client.update_source(
                token=token,
                config_id=config_id,
                comment=comment,
                is_hidden=is_hidden,
                max_depth=max_depth,
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Operations
    # ═══════════════════════════════════════════════════════════════════════

    def refresh_subscription(self, token: str) -> RefreshSubscriptionResponse:
        """Manually refresh external URL sources."""
        return self._run(self._async_client.refresh_subscription(token))

    # ═══════════════════════════════════════════════════════════════════════
    # Public Endpoints
    # ═══════════════════════════════════════════════════════════════════════

    def get_public_subscription(self, token: str) -> PublicSubscriptionResponse:
        """Get public subscription configs (base64 encoded)."""
        return self._run(self._async_client.get_public_subscription(token))
