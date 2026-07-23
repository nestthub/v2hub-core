"""
Contract test for the public v2hub package surface.

This does not test behavior, only that names importable from `v2hub` today
remain importable after an update. If a name is intentionally removed or
renamed as part of the update, this test should be updated deliberately
(not silently broken) so the change is visible in the diff/changelog.
"""

from __future__ import annotations

from typing import ClassVar

import v2hub

EXPECTED_EXPORTS = {
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
}


class TestPublicAPISurface:
    def test_all_matches_expected_exports(self):
        assert set(v2hub.__all__) == EXPECTED_EXPORTS

    def test_every_declared_export_is_actually_importable(self):
        missing = [name for name in v2hub.__all__ if not hasattr(v2hub, name)]
        assert missing == []

    def test_version_is_a_string(self):
        assert isinstance(v2hub.__version__, str)
        assert v2hub.__version__

    def test_api_version_is_v1(self):
        # Bumping this changes every endpoint URL the clients call.
        assert v2hub.__api_version__ == "v1"

    def test_async_client_is_the_full_featured_client(self):
        from v2hub.async_client import AsyncVPNClient

        assert v2hub.AsyncVPNClient is AsyncVPNClient

    def test_sync_client_is_the_wrapper(self):
        from v2hub.client import VPNClient

        assert v2hub.VPNClient is VPNClient


class TestAsyncVPNClientMethodSurface:
    """
    Pin down the set of public methods on AsyncVPNClient. If the update
    adds new methods (e.g. for is_hidden/max_depth or a new update-source
    endpoint) that's expected and this set should grow; if it silently
    removes/renames an existing method, that's a breaking change this
    test will catch.
    """

    EXPECTED_METHODS: ClassVar[set[str]] = {
        "list_subscriptions",
        "create_subscription",
        "get_subscription",
        "get_subscription_by_name",
        "update_subscription",
        "delete_subscription",
        "add_sources",
        "replace_sources",
        "remove_sources",
        "update_comment",
        "refresh_subscription",
        "get_public_subscription",
        "connect",
        "close",
    }

    def test_has_all_expected_methods(self):
        from v2hub.async_client import AsyncVPNClient

        actual = {
            name
            for name in dir(AsyncVPNClient)
            if not name.startswith("_") and callable(getattr(AsyncVPNClient, name))
        }
        missing = self.EXPECTED_METHODS - actual
        assert missing == set(), f"Methods removed or renamed: {missing}"


class TestVPNClientMethodSurface:
    EXPECTED_METHODS: ClassVar[set[str]] = {
        "list_subscriptions",
        "create_subscription",
        "get_subscription",
        "get_subscription_by_name",
        "update_subscription",
        "delete_subscription",
        "add_sources",
        "replace_sources",
        "remove_sources",
        "update_comment",
        "refresh_subscription",
        "get_public_subscription",
    }

    def test_has_all_expected_methods(self):
        from v2hub.client import VPNClient

        actual = {
            name
            for name in dir(VPNClient)
            if not name.startswith("_") and callable(getattr(VPNClient, name))
        }
        missing = self.EXPECTED_METHODS - actual
        assert missing == set(), f"Methods removed or renamed: {missing}"
