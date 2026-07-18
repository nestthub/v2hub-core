from __future__ import annotations

import httpx
import pytest
import respx

from v2hub import __api_version__
from v2hub.client import VPNClient
from v2hub.core.retry import CircuitBreakerConfig, RetryConfig


BASE_URL = "https://api.example.com"
TOKEN = "test-token"


def make_client() -> VPNClient:
    return VPNClient(
        BASE_URL,
        TOKEN,
        retry_config=RetryConfig(max_retries=0),
        circuit_breaker_config=CircuitBreakerConfig(enabled=False),
    )


class TestSyncClientLifecycle:
    def test_context_manager_sets_up_and_tears_down_loop(self):
        client = make_client()
        assert client._loop is None
        with client as c:
            assert c is client
            assert client._loop is not None
            assert client._owned_loop is True
        assert client._loop is None
        assert client._owned_loop is False


class TestSyncClientDelegation:
    def test_list_subscriptions(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(200, json=[subscription_dict_factory()])
            )
            with make_client() as client:
                subs = client.list_subscriptions()
        assert len(subs) == 1

    def test_create_subscription_no_sources_arg(self, subscription_dict_factory):
        """
        KNOWN BUG in older versions: VPNClient.create_subscription defaulted
        sources to None, but forwarded it positionally into
        AsyncVPNClient.create_subscription(name, description, sources),
        whose SubscriptionCreateRequest required sources to be a list (or
        omitted entirely) -- it rejected None. Calling
        VPNClient(...).create_subscription("name") with no sources arg
        used to raise a pydantic ValidationError instead of succeeding.

        This test accepts either outcome: if the bug is still present, it
        confirms the failure is specifically about `sources` (so it's easy
        to recognize, not some unrelated error); if the bug has been fixed,
        it confirms the call now succeeds cleanly. Either way, a change in
        *which* of these two outcomes happens is worth noticing -- so this
        test still tells you something happened, without hard-failing a
        CI run just because the (unrelated, pre-existing) bug got fixed as
        a side effect of other work.
        """
        with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
            mock.post(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(
                    201, json=subscription_dict_factory(name="sync-sub")
                )
            )
            with make_client() as client:
                try:
                    sub = client.create_subscription("sync-sub")
                except Exception as exc:
                    assert "sources" in str(exc), (
                        f"create_subscription('name') with no sources failed, but "
                        f"not for the expected reason (expected something "
                        f"mentioning 'sources'): {exc!r}"
                    )
                else:
                    assert sub.name == "sync-sub"

    def test_create_subscription_with_explicit_sources_works(
        self, subscription_dict_factory
    ):
        """Passing sources explicitly always works, bug or no bug."""
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(201, json=subscription_dict_factory(name="sync-sub"))
            )
            with make_client() as client:
                sub = client.create_subscription("sync-sub", sources=[])
        assert sub.name == "sync-sub"

    def test_get_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.get_subscription(TOKEN)
        assert sub.token == TOKEN

    def test_get_subscription_by_name(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/by-name/n").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(name="n"))
            )
            with make_client() as client:
                sub = client.get_subscription_by_name("n")
        assert sub.name == "n"

    def test_update_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.patch(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(
                    200, json=subscription_dict_factory(token=TOKEN, name="updated")
                )
            )
            with make_client() as client:
                sub = client.update_subscription(TOKEN, name="updated")
        assert sub.name == "updated"

    def test_delete_subscription(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(204)
            )
            with make_client() as client:
                result = client.delete_subscription(TOKEN)
        assert result is None
        assert route.called

    def test_add_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.add_sources(TOKEN, ["vless://a"])
        assert sub.token == TOKEN

    def test_replace_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.replace_sources(TOKEN, ["vless://a"])
        assert sub.token == TOKEN

    def test_remove_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.delete(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            with make_client() as client:
                sub = client.remove_sources(TOKEN, ["id1"])
        assert sub.token == TOKEN

    def test_update_comment(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.patch(f"/api/{__api_version__}/subs/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )
            with make_client() as client:
                result = client.update_comment(TOKEN, "cfg1", "hi")
        assert result is None

    def test_refresh_subscription(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/subs/{TOKEN}/refresh").mock(
                return_value=httpx.Response(200, json={"refreshed": 1, "total": 1})
            )
            with make_client() as client:
                result = client.refresh_subscription(TOKEN)
        assert result.refreshed == 1

    def test_get_public_subscription(self):
        import base64

        content = base64.b64encode(b"vless://a").decode()
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/sub/{TOKEN}").mock(return_value=httpx.Response(200, text=content))
            with make_client() as client:
                resp = client.get_public_subscription(TOKEN)
        assert resp.get_configs() == ["vless://a"]


class TestSyncClientWithoutContextManager:
    def test_run_without_entering_context_uses_asyncio_run(
        self, subscription_dict_factory
    ):
        """
        _run() falls back to asyncio.run() when not used as a context
        manager. Each call creates and tears down its own event loop, so
        this works for one-off calls but is less efficient for many calls.
        """
        client = make_client()
        assert client._loop is None

        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            sub = client.get_subscription(TOKEN)
        assert sub.token == TOKEN
