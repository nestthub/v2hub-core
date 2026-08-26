from __future__ import annotations

import json

import httpx
import pytest
import respx

from v2hub import __api_version__
from v2hub.async_client import AsyncVPNClient
from v2hub.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from v2hub.core.retry import CircuitBreakerConfig, RetryConfig
from v2hub.models import Subscription

from ._helpers import wire_source_data_list

BASE_URL = "https://api.example.com"
TOKEN = "test-token"
PROVIDER_TOKEN = "provider-token"
USER_ID = 123


def make_client(*, api_token: str = PROVIDER_TOKEN) -> AsyncVPNClient:
    return AsyncVPNClient(
        BASE_URL,
        api_token,
        retry_config=RetryConfig(max_retries=0),
        circuit_breaker_config=CircuitBreakerConfig(enabled=False),
    )


def provider_prefix(user_id: int = USER_ID) -> str:
    return f"/api/{__api_version__}/providers/{user_id}/subs"


def self_prefix() -> str:
    return f"/api/{__api_version__}/subs"


def provider_connection_response(
    user_id: int,
    *,
    status: str = "pending",
) -> dict:
    return {
        "user_id": user_id,
        "status": status,
    }


def provider_connection_create_response(
    user_id: int,
    *,
    status: str = "pending",
    connection_link: str | None = "https://t.me/v2hubot?start=provider_vpn123",
) -> dict:
    return {
        "user_id": user_id,
        "status": status,
        "connection_link": connection_link,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Path routing: default (self-service) vs. as_provider_for_user_id set
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderPathRouting:
    async def test_default_is_self_service_path_not_provider_path(
        self,
        subscription_dict_factory,
    ):
        """Omitting as_provider_for_user_id must never touch /providers/..."""
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )
            async with make_client() as client:
                await client.list_subscriptions()

        assert self_route.called

    async def test_as_provider_for_user_id_none_explicit_uses_self_service_path(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )
            async with make_client() as client:
                await client.list_subscriptions(
                    as_provider_for_user_id=None,
                )

        assert self_route.called

    async def test_as_provider_for_user_id_set_uses_provider_path(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            provider_route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )
            async with make_client() as client:
                await client.list_subscriptions(
                    as_provider_for_user_id=USER_ID,
                )

        assert provider_route.called

    async def test_as_provider_for_user_id_is_keyword_only(self):
        """
        Passing it positionally must raise a TypeError -- this is the whole
        point of making it keyword-only, so a developer can't accidentally
        pass a user id into some other positional slot.
        """
        async with make_client() as client:
            with pytest.raises(TypeError):
                await client.get_subscription(TOKEN, USER_ID)  # type: ignore[misc]

    async def test_different_user_ids_produce_different_paths(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            route_a = mock.get(provider_prefix(111)).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )
            route_b = mock.get(provider_prefix(222)).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )

            async with make_client() as client:
                await client.list_subscriptions(
                    as_provider_for_user_id=111,
                )
                await client.list_subscriptions(
                    as_provider_for_user_id=222,
                )

        assert route_a.called
        assert route_b.called
        assert route_a.call_count == 1
        assert route_b.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Subscription management, as provider
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderCreateSubscription:
    async def test_creates_for_target_user_not_provider_account(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(
                    201,
                    json=subscription_dict_factory(name="customer-vpn"),
                )
            )

            async with make_client() as client:
                sub = await client.create_subscription(
                    "customer-vpn",
                    as_provider_for_user_id=USER_ID,
                )

        assert isinstance(sub, Subscription)
        payload = json.loads(route.calls.last.request.content)
        assert payload["name"] == "customer-vpn"

    async def test_sources_reach_provider_endpoint(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(
                    201,
                    json=subscription_dict_factory(),
                )
            )

            async with make_client() as client:
                await client.create_subscription(
                    "vpn",
                    sources=["vless://a"],
                    as_provider_for_user_id=USER_ID,
                )

        payload = json.loads(route.calls.last.request.content)
        assert wire_source_data_list(payload["sources"]) == ["vless://a"]


class TestProviderGetSubscription:
    async def test_by_token(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                sub = await client.get_subscription(
                    TOKEN,
                    as_provider_for_user_id=USER_ID,
                )

        assert sub.token == TOKEN

    async def test_does_not_hit_self_service_path(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
            self_route = mock.get(f"{self_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )
            mock.get(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                await client.get_subscription(
                    TOKEN,
                    as_provider_for_user_id=USER_ID,
                )

        assert not self_route.called


class TestProviderUpdateSubscription:
    async def test_patches_provider_path(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(
                        token=TOKEN,
                        name="renamed",
                    ),
                )
            )

            async with make_client() as client:
                sub = await client.update_subscription(
                    TOKEN,
                    name="renamed",
                    as_provider_for_user_id=USER_ID,
                )

        assert sub.name == "renamed"
        assert route.called


class TestProviderDeleteSubscription:
    async def test_deletes_via_provider_path(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(204)
            )

            async with make_client() as client:
                result = await client.delete_subscription(
                    TOKEN,
                    as_provider_for_user_id=USER_ID,
                )

        assert result is None
        assert route.called


# ═══════════════════════════════════════════════════════════════════════════
# Source management, as provider
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderSourceManagement:
    async def test_add_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                sub = await client.add_sources(
                    TOKEN,
                    ["vless://a"],
                    as_provider_for_user_id=USER_ID,
                )

        assert sub.token == TOKEN
        assert route.called

    async def test_replace_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.put(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                sub = await client.replace_sources(
                    TOKEN,
                    ["vless://only"],
                    as_provider_for_user_id=USER_ID,
                )

        assert sub.token == TOKEN
        assert route.called

    async def test_remove_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                await client.remove_sources(
                    TOKEN,
                    ["id1"],
                    as_provider_for_user_id=USER_ID,
                )

        payload = json.loads(route.calls.last.request.content)
        assert payload == {"source_ids": ["id1"]}

    async def test_update_source_partial_patch(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"{provider_prefix()}/{TOKEN}/config").mock(
                return_value=httpx.Response(204)
            )

            async with make_client() as client:
                await client.update_source(
                    TOKEN,
                    "cfg1",
                    is_hidden=True,
                    as_provider_for_user_id=USER_ID,
                )

        payload = json.loads(route.calls.last.request.content)
        assert payload == {
            "config_id": "cfg1",
            "is_hidden": True,
        }

    async def test_update_comment_deprecated_still_routes_to_provider_path(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"{provider_prefix()}/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )

            async with make_client() as client:
                await client.update_comment(
                    TOKEN,
                    "cfg1",
                    "hi",
                    as_provider_for_user_id=USER_ID,
                )

        assert route.called


# ═══════════════════════════════════════════════════════════════════════════
# Operations, as provider
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderRefreshSubscription:
    async def test_refresh_uses_provider_path(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"{provider_prefix()}/{TOKEN}/refresh").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "refreshed": 1,
                        "failed": 0,
                        "skipped": 0,
                        "total": 1,
                    },
                )
            )

            async with make_client() as client:
                result = await client.refresh_subscription(
                    TOKEN,
                    as_provider_for_user_id=USER_ID,
                )

        assert result.refreshed == 1
        assert route.called


# ═══════════════════════════════════════════════════════════════════════════
# One client, multiple end-users
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderMultiUserSingleClient:
    async def test_same_client_serves_self_service_and_multiple_providers(
        self,
        subscription_dict_factory,
    ):
        """
        A single client/connection must be able to freely mix self-service
        calls and provider calls for different end-users, call by call.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory(token="self1")],
                )
            )
            user_a_route = mock.get(provider_prefix(111)).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory(token="a1")],
                )
            )
            user_b_route = mock.get(provider_prefix(222)).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory(token="b1")],
                )
            )

            async with make_client() as client:
                own = await client.list_subscriptions()
                a = await client.list_subscriptions(
                    as_provider_for_user_id=111,
                )
                b = await client.list_subscriptions(
                    as_provider_for_user_id=222,
                )

        assert [s.token for s in own] == ["self1"]
        assert [s.token for s in a] == ["a1"]
        assert [s.token for s in b] == ["b1"]
        assert self_route.call_count == 1
        assert user_a_route.call_count == 1
        assert user_b_route.call_count == 1

    async def test_create_then_add_sources_for_same_target_user(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            create_route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(
                    201,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )
            add_route = mock.post(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(
                    200,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                sub = await client.create_subscription(
                    "vpn",
                    as_provider_for_user_id=USER_ID,
                )
                await client.add_sources(
                    sub.token,
                    ["vless://a"],
                    as_provider_for_user_id=USER_ID,
                )

        assert create_route.called
        assert add_route.called


# ═══════════════════════════════════════════════════════════════════════════
# Validation still runs before the request is sent, in provider mode too
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderClientSideValidation:
    async def test_add_sources_empty_list_raises_before_request(self):
        async with make_client() as client:
            with pytest.raises(ValidationError):
                await client.add_sources(
                    TOKEN,
                    [],
                    as_provider_for_user_id=USER_ID,
                )

    async def test_update_subscription_neither_field_raises_before_request(self):
        async with make_client() as client:
            with pytest.raises(ValidationError):
                await client.update_subscription(
                    TOKEN,
                    as_provider_for_user_id=USER_ID,
                )


# ═══════════════════════════════════════════════════════════════════════════
# Provider Connection Management
# ═══════════════════════════════════════════════════════════════════════════


class TestGetProviderConnection:
    async def test_returns_pending_status(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    200,
                    json=provider_connection_response(USER_ID),
                )
            )

            async with make_client() as client:
                conn = await client.get_provider_connection(USER_ID)

        assert conn.user_id == USER_ID
        assert conn.status == "pending"
        assert route.called

    async def test_returns_approved_status(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    200,
                    json=provider_connection_response(
                        USER_ID,
                        status="approved",
                    ),
                )
            )

            async with make_client() as client:
                conn = await client.get_provider_connection(USER_ID)

        assert conn.user_id == USER_ID
        assert conn.status == "approved"
        assert route.called

    async def test_not_found_raises(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    404,
                    json={"message": "not found"},
                )
            )

            async with make_client() as client:
                with pytest.raises(NotFoundError):
                    await client.get_provider_connection(USER_ID)


class TestCreateProviderConnection:
    async def test_posts_to_provider_path_and_returns_pending(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    201,
                    json=provider_connection_create_response(USER_ID),
                )
            )

            async with make_client() as client:
                conn = await client.create_provider_connection(USER_ID)

        assert conn.user_id == USER_ID
        assert conn.status == "pending"
        assert conn.connection_link is not None
        assert route.called

    async def test_different_user_ids_hit_different_paths(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route_a = mock.post(f"/api/{__api_version__}/providers/111").mock(
                return_value=httpx.Response(
                    201,
                    json=provider_connection_create_response(111),
                )
            )
            route_b = mock.post(f"/api/{__api_version__}/providers/222").mock(
                return_value=httpx.Response(
                    201,
                    json=provider_connection_create_response(222),
                )
            )

            async with make_client() as client:
                conn_a = await client.create_provider_connection(111)
                conn_b = await client.create_provider_connection(222)

        assert conn_a.user_id == 111
        assert conn_b.user_id == 222
        assert conn_a.status == "pending"
        assert conn_b.status == "pending"
        assert conn_a.connection_link is not None
        assert conn_b.connection_link is not None
        assert route_a.called
        assert route_b.called


class TestRevokeProviderConnection:
    async def test_posts_to_revoke_path(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}/revoke").mock(
                return_value=httpx.Response(
                    200,
                    json=provider_connection_response(
                        USER_ID,
                        status="revoked",
                    ),
                )
            )

            async with make_client() as client:
                conn = await client.revoke_provider_connection(USER_ID)

        assert conn.user_id == USER_ID
        assert conn.status == "revoked"
        assert route.called

    async def test_no_existing_authorization_raises(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/providers/{USER_ID}/revoke").mock(
                return_value=httpx.Response(
                    401,
                    json={"message": "Authorization not found"},
                )
            )

            async with make_client() as client:
                with pytest.raises(AuthenticationError):
                    await client.revoke_provider_connection(USER_ID)


class TestDeleteProviderConnection:
    async def test_calls_delete_on_provider_path(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    200,
                    json={"detail": "Provider connection deleted"},
                )
            )

            async with make_client() as client:
                result = await client.delete_provider_connection(USER_ID)

        assert result.detail == "Provider connection deleted"
        assert route.called

    async def test_does_not_touch_subs_path(self):
        """Deleting a connection must hit /providers/{id}, never /providers/{id}/subs."""
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
            conn_route = mock.delete(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    200,
                    json={"detail": "Provider connection deleted"},
                )
            )
            subs_route = mock.delete(provider_prefix()).mock(return_value=httpx.Response(204))

            async with make_client() as client:
                await client.delete_provider_connection(USER_ID)

        assert conn_route.called
        assert not subs_route.called


class TestProviderConnectionFlowIntegration:
    async def test_create_connection_returns_pending_and_does_not_imply_access(self):
        """
        Creating a provider connection now creates a PENDING authorization.
        The client must not treat the response as an approved connection.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            connect_route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    201,
                    json=provider_connection_create_response(USER_ID),
                )
            )

            async with make_client() as client:
                conn = await client.create_provider_connection(USER_ID)

        assert conn.user_id == USER_ID
        assert conn.status == "pending"
        assert conn.connection_link is not None
        assert connect_route.called

    async def test_approved_connection_can_then_manage_subscription(
        self,
        subscription_dict_factory,
    ):
        """
        Provider subscription operations are tested independently with an
        already-approved connection. This keeps the test focused on the
        client routing contract rather than assuming that creating a new
        connection grants access immediately.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            create_sub_route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(
                    201,
                    json=subscription_dict_factory(token=TOKEN),
                )
            )

            async with make_client() as client:
                sub = await client.create_subscription(
                    "vpn",
                    as_provider_for_user_id=USER_ID,
                )

        assert sub.token == TOKEN
        assert create_sub_route.called


# ═══════════════════════════════════════════════════════════════════════════
# Provider authentication
# ═══════════════════════════════════════════════════════════════════════════
#
# The provider "context" is not a separate client type or a separate
# constructor argument -- it's just the value of `api_token`, exactly like
# a regular user token. The client doesn't parse or validate the token;
# the server decides what it's authorized for.


class TestProviderAuthentication:
    async def test_provider_token_sent_as_api_token_header(
        self,
        subscription_dict_factory,
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )

            async with make_client(api_token=PROVIDER_TOKEN) as client:
                await client.list_subscriptions(as_provider_for_user_id=USER_ID)

        sent_headers = route.calls.last.request.headers
        assert sent_headers["API-Token"] == PROVIDER_TOKEN

    async def test_regular_user_token_unaffected_by_provider_support(
        self,
        subscription_dict_factory,
    ):
        """
        A plain user token, used without as_provider_for_user_id, must
        send exactly the same header it always did.
        """
        user_token = "plain-user-token"

        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )

            async with make_client(api_token=user_token) as client:
                await client.list_subscriptions()

        sent_headers = route.calls.last.request.headers
        assert sent_headers["API-Token"] == user_token

    async def test_same_client_token_used_for_both_self_service_and_provider_calls(
        self,
        subscription_dict_factory,
    ):
        """
        One client/one token can freely mix self-service and provider calls.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )
            provider_route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(
                    200,
                    json=[subscription_dict_factory()],
                )
            )

            async with make_client(api_token=PROVIDER_TOKEN) as client:
                await client.list_subscriptions()
                await client.list_subscriptions(as_provider_for_user_id=USER_ID)

        assert self_route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN
        assert provider_route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN

    async def test_provider_connection_calls_also_send_provider_token(self):
        """
        Provider connection management calls must carry the configured
        provider token.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(
                    201,
                    json=provider_connection_create_response(USER_ID),
                )
            )

            async with make_client(api_token=PROVIDER_TOKEN) as client:
                await client.create_provider_connection(USER_ID)

        assert route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN

    async def test_invalid_token_yields_authentication_error_regardless_of_mode(
        self,
    ):
        """
        The client applies no client-side notion of "provider token".
        The server is responsible for token validation.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(provider_prefix()).mock(
                return_value=httpx.Response(
                    401,
                    json={"message": "invalid token"},
                )
            )

            async with make_client(api_token="not-a-real-token") as client:
                with pytest.raises(AuthenticationError):
                    await client.list_subscriptions(as_provider_for_user_id=USER_ID)
