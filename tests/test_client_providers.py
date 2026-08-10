from __future__ import annotations

import json

import httpx
import pytest
import respx

from v2hub import __api_version__
from v2hub.client import VPNClient
from v2hub.core.retry import CircuitBreakerConfig, RetryConfig

BASE_URL = "https://api.example.com"
TOKEN = "test-token"
PROVIDER_TOKEN = "provider-token"
USER_ID = 123


def make_client(*, api_token: str = PROVIDER_TOKEN) -> VPNClient:
    return VPNClient(
        BASE_URL,
        api_token,
        retry_config=RetryConfig(max_retries=0),
        circuit_breaker_config=CircuitBreakerConfig(enabled=False),
    )


def provider_prefix(user_id: int = USER_ID) -> str:
    return f"/api/{__api_version__}/providers/{user_id}/subs"


def self_prefix() -> str:
    return f"/api/{__api_version__}/subs"


class TestSyncClientProviderPathRouting:
    def test_default_uses_self_service_path(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client() as client:
                client.list_subscriptions()
        assert route.called

    def test_as_provider_for_user_id_uses_provider_path(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client() as client:
                client.list_subscriptions(as_provider_for_user_id=USER_ID)
        assert route.called

    def test_as_provider_for_user_id_is_keyword_only(self):
        with make_client() as client, pytest.raises(TypeError):
            client.get_subscription(TOKEN, USER_ID)  # type: ignore[misc]


class TestSyncClientProviderDelegation:
    def test_create_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(
                    201, json=subscription_dict_factory(name="customer-vpn")
                )
            )
            with make_client() as client:
                sub = client.create_subscription("customer-vpn", as_provider_for_user_id=USER_ID)
        assert sub.name == "customer-vpn"
        assert route.called

    def test_get_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.get_subscription(TOKEN, as_provider_for_user_id=USER_ID)
        assert sub.token == TOKEN

    def test_update_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.patch(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(
                    200, json=subscription_dict_factory(token=TOKEN, name="updated")
                )
            )
            with make_client() as client:
                sub = client.update_subscription(
                    TOKEN, name="updated", as_provider_for_user_id=USER_ID
                )
        assert sub.name == "updated"

    def test_delete_subscription(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"{provider_prefix()}/{TOKEN}").mock(
                return_value=httpx.Response(204)
            )
            with make_client() as client:
                result = client.delete_subscription(TOKEN, as_provider_for_user_id=USER_ID)
        assert result is None
        assert route.called

    def test_add_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.add_sources(TOKEN, ["vless://a"], as_provider_for_user_id=USER_ID)
        assert sub.token == TOKEN

    def test_replace_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.replace_sources(TOKEN, ["vless://a"], as_provider_for_user_id=USER_ID)
        assert sub.token == TOKEN

    def test_remove_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.delete(f"{provider_prefix()}/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.remove_sources(TOKEN, ["id1"], as_provider_for_user_id=USER_ID)
        assert sub.token == TOKEN

    def test_update_source(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"{provider_prefix()}/{TOKEN}/config").mock(
                return_value=httpx.Response(204)
            )
            with make_client() as client:
                client.update_source(TOKEN, "cfg1", is_hidden=True, as_provider_for_user_id=USER_ID)
        payload = json.loads(route.calls.last.request.content)
        assert payload == {"config_id": "cfg1", "is_hidden": True}

    def test_update_comment(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"{provider_prefix()}/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )
            with make_client() as client:
                result = client.update_comment(TOKEN, "cfg1", "hi", as_provider_for_user_id=USER_ID)
        assert result is None
        assert route.called

    def test_refresh_subscription(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"{provider_prefix()}/{TOKEN}/refresh").mock(
                return_value=httpx.Response(200, json={"refreshed": 1, "total": 1})
            )
            with make_client() as client:
                result = client.refresh_subscription(TOKEN, as_provider_for_user_id=USER_ID)
        assert result.refreshed == 1
        assert route.called


class TestSyncClientProviderMultiUserSingleClient:
    def test_same_client_mixes_self_service_and_multiple_providers(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory(token="self1")])
            )
            user_a_route = mock.get(provider_prefix(111)).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory(token="a1")])
            )
            user_b_route = mock.get(provider_prefix(222)).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory(token="b1")])
            )

            with make_client() as client:
                own = client.list_subscriptions()
                a = client.list_subscriptions(as_provider_for_user_id=111)
                b = client.list_subscriptions(as_provider_for_user_id=222)

        assert [s.token for s in own] == ["self1"]
        assert [s.token for s in a] == ["a1"]
        assert [s.token for s in b] == ["b1"]
        assert self_route.call_count == 1
        assert user_a_route.call_count == 1
        assert user_b_route.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Provider Connection Management
# ═══════════════════════════════════════════════════════════════════════════


class TestSyncClientProviderConnectionManagement:
    def test_get_provider_connection(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(200, json={"user_id": USER_ID, "status": "approved"})
            )
            with make_client() as client:
                conn = client.get_provider_connection(USER_ID)
        assert conn.user_id == USER_ID
        assert conn.status == "approved"
        assert route.called

    def test_create_provider_connection(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(201, json={"user_id": USER_ID, "status": "approved"})
            )
            with make_client() as client:
                conn = client.create_provider_connection(USER_ID)
        assert conn.status == "approved"
        assert route.called

    def test_revoke_provider_connection(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}/revoke").mock(
                return_value=httpx.Response(200, json={"user_id": USER_ID, "status": "revoked"})
            )
            with make_client() as client:
                conn = client.revoke_provider_connection(USER_ID)
        assert conn.status == "revoked"
        assert route.called

    def test_delete_provider_connection(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(200, json={"detail": "Provider connection deleted"})
            )
            with make_client() as client:
                result = client.delete_provider_connection(USER_ID)
        assert result.detail == "Provider connection deleted"
        assert route.called

    def test_create_connection_then_manage_subscription(self, subscription_dict_factory):
        """End-to-end composition: connect, then act as provider for that user."""
        with respx.mock(base_url=BASE_URL) as mock:
            connect_route = mock.post(f"/api/{__api_version__}/providers/{USER_ID}").mock(
                return_value=httpx.Response(201, json={"user_id": USER_ID, "status": "approved"})
            )
            create_sub_route = mock.post(provider_prefix()).mock(
                return_value=httpx.Response(201, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                conn = client.create_provider_connection(USER_ID)
                assert conn.status == "approved"
                sub = client.create_subscription("vpn", as_provider_for_user_id=USER_ID)
        assert sub.token == TOKEN
        assert connect_route.called
        assert create_sub_route.called


# ═══════════════════════════════════════════════════════════════════════════
# Provider authentication
# ═══════════════════════════════════════════════════════════════════════════


class TestSyncClientProviderAuthentication:
    def test_provider_token_sent_as_api_token_header(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client(api_token=PROVIDER_TOKEN) as client:
                client.list_subscriptions(as_provider_for_user_id=USER_ID)
        assert route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN

    def test_regular_user_token_unaffected_by_provider_support(self, subscription_dict_factory):
        user_token = "plain-user-token"
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client(api_token=user_token) as client:
                client.list_subscriptions()
        assert route.calls.last.request.headers["API-Token"] == user_token

    def test_same_client_token_used_for_both_self_service_and_provider_calls(
        self, subscription_dict_factory
    ):
        with respx.mock(base_url=BASE_URL) as mock:
            self_route = mock.get(self_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            provider_route = mock.get(provider_prefix()).mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client(api_token=PROVIDER_TOKEN) as client:
                client.list_subscriptions()
                client.list_subscriptions(as_provider_for_user_id=USER_ID)
        assert self_route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN
        assert provider_route.calls.last.request.headers["API-Token"] == PROVIDER_TOKEN
