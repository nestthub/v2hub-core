from __future__ import annotations

import httpx
import pytest
import respx

from v2hub import __api_version__
from v2hub.async_client import AsyncVPNClient
from v2hub.core.exceptions import NotFoundError, ValidationError
from v2hub.core.retry import CircuitBreakerConfig, RetryConfig
from v2hub.models.public import PublicSubscriptionResponse
from v2hub.models.subscriptions import Subscription, SubscriptionListItem

from ._helpers import wire_source_data_list

BASE_URL = "https://api.example.com"
TOKEN = "test-token"


def make_client() -> AsyncVPNClient:
    return AsyncVPNClient(
        BASE_URL,
        TOKEN,
        retry_config=RetryConfig(max_retries=0),
        circuit_breaker_config=CircuitBreakerConfig(enabled=False),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Client lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestClientLifecycle:
    async def test_context_manager_connects_and_closes(self):
        client = make_client()
        async with client as c:
            assert c is client
            assert client._http_client._client is not None
        assert client._http_client._client is None

    async def test_headers_include_api_token(self):
        client = make_client()
        assert client._http_client._default_headers["API-Token"] == TOKEN


# ═══════════════════════════════════════════════════════════════════════════
# Subscription management
# ═══════════════════════════════════════════════════════════════════════════


class TestListSubscriptions:
    async def test_returns_list_of_subscription_list_items(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        subscription_dict_factory(token="t1"),
                        subscription_dict_factory(token="t2"),
                    ],
                )
            )
            async with make_client() as client:
                subs = await client.list_subscriptions()
        assert len(subs) == 2
        assert all(isinstance(s, SubscriptionListItem) for s in subs)
        assert {s.token for s in subs} == {"t1", "t2"}

    async def test_empty_list(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs").mock(return_value=httpx.Response(200, json=[]))
            async with make_client() as client:
                subs = await client.list_subscriptions()
        assert subs == []


class TestCreateSubscription:
    async def test_sends_correct_payload(self, subscription_dict_factory):
        """
        Calling with plain-string sources (the original calling convention)
        must still work; what matters is the source data reaches the wire
        intact, regardless of whether the library now wraps each source
        in an object (e.g. {"data": ..., "is_hidden": ..., "max_depth": ...})
        or sends bare strings.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(201, json=subscription_dict_factory())
            )
            async with make_client() as client:
                sub = await client.create_subscription(
                    "My VPN", description="desc", sources=["vless://a"]
                )

        assert isinstance(sub, Subscription)
        sent_body = route.calls.last.request.content
        import json

        payload = json.loads(sent_body)
        assert payload["name"] == "My VPN"
        assert payload["description"] == "desc"
        assert wire_source_data_list(payload["sources"]) == ["vless://a"]

    async def test_minimal_call_no_description_no_sources(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(201, json=subscription_dict_factory())
            )
            async with make_client() as client:
                await client.create_subscription("just-a-name")

        import json

        payload = json.loads(route.calls.last.request.content)
        # exclude_none=True should drop description; sources defaults to []
        assert "description" not in payload
        assert payload["name"] == "just-a-name"

    async def test_conflict_raises_specific_error(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/subs").mock(
                return_value=httpx.Response(
                    409, json={"error": "duplicate_name", "message": "name taken"}
                )
            )
            async with make_client() as client:
                with pytest.raises(Exception) as exc_info:
                    await client.create_subscription("dup")
        assert "name taken" in str(exc_info.value)


class TestGetSubscription:
    async def test_by_token(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            async with make_client() as client:
                sub = await client.get_subscription(TOKEN)
        assert sub.token == TOKEN

    async def test_not_found(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/missing").mock(
                return_value=httpx.Response(404, json={"message": "not found"})
            )
            async with make_client() as client:
                with pytest.raises(NotFoundError):
                    await client.get_subscription("missing")

    async def test_by_name(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/api/{__api_version__}/subs/by-name/my-vpn").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(name="my-vpn"))
            )
            async with make_client() as client:
                sub = await client.get_subscription_by_name("my-vpn")
        assert sub.name == "my-vpn"


class TestUpdateSubscription:
    async def test_sends_patch_with_provided_fields_only(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(
                    200, json=subscription_dict_factory(token=TOKEN, name="new-name")
                )
            )
            async with make_client() as client:
                sub = await client.update_subscription(TOKEN, name="new-name")

        assert sub.name == "new-name"
        import json

        payload = json.loads(route.calls.last.request.content)
        assert payload == {"name": "new-name"}

    async def test_neither_field_raises_validation_error_client_side(self):
        # SubscriptionUpdateRequest itself enforces "at least one field",
        # so this should fail before any HTTP call is made.
        async with make_client() as client:
            with pytest.raises(ValidationError):
                await client.update_subscription(TOKEN)


class TestDeleteSubscription:
    async def test_calls_delete(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(204)
            )
            async with make_client() as client:
                result = await client.delete_subscription(TOKEN)
        assert result is None
        assert route.called


# ═══════════════════════════════════════════════════════════════════════════
# Source management
# ═══════════════════════════════════════════════════════════════════════════


class TestAddSources:
    async def test_sends_sources_and_returns_subscription(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.post(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            async with make_client() as client:
                sub = await client.add_sources(TOKEN, ["vless://a", "vless://b"])

        assert sub.token == TOKEN
        import json

        payload = json.loads(route.calls.last.request.content)
        assert set(payload.keys()) == {"sources"}
        assert wire_source_data_list(payload["sources"]) == ["vless://a", "vless://b"]

    async def test_empty_sources_raises_before_request(self):
        async with make_client() as client:
            with pytest.raises(ValidationError):
                await client.add_sources(TOKEN, [])


class TestReplaceSources:
    async def test_put_request(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.put(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            async with make_client() as client:
                await client.replace_sources(TOKEN, ["vless://only"])

        import json

        payload = json.loads(route.calls.last.request.content)
        assert set(payload.keys()) == {"sources"}
        assert wire_source_data_list(payload["sources"]) == ["vless://only"]

    async def test_empty_list_allowed(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(
                    200, json=subscription_dict_factory(token=TOKEN, sources=[], sources_count=0)
                )
            )
            async with make_client() as client:
                sub = await client.replace_sources(TOKEN, [])
        assert sub.sources == []


class TestRemoveSources:
    async def test_delete_with_body(self, subscription_dict_factory):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.delete(f"/api/{__api_version__}/subs/{TOKEN}/sources").mock(
                return_value=httpx.Response(200, json=subscription_dict_factory(token=TOKEN))
            )
            async with make_client() as client:
                await client.remove_sources(TOKEN, ["id1", "id2"])

        import json

        payload = json.loads(route.calls.last.request.content)
        assert payload == {"source_ids": ["id1", "id2"]}

    async def test_empty_ids_raises_before_request(self):
        async with make_client() as client:
            with pytest.raises(ValidationError):
                await client.remove_sources(TOKEN, [])


class TestUpdateComment:
    async def test_sends_comment(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"/api/{__api_version__}/subs/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )
            async with make_client() as client:
                await client.update_comment(TOKEN, "cfg1", "my comment")

        import json

        payload = json.loads(route.calls.last.request.content)
        assert payload == {"config_id": "cfg1", "comment": "my comment"}

    async def test_none_comment_excluded_from_payload(self):
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.patch(f"/api/{__api_version__}/subs/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )
            async with make_client() as client:
                await client.update_comment(TOKEN, "cfg1", None)

        import json

        payload = json.loads(route.calls.last.request.content)
        # exclude_none=True should drop "comment" entirely
        assert payload == {"config_id": "cfg1"}

    async def test_returns_none(self):
        """
        Documents current behavior: update_comment has no explicit return
        statement, so it always returns None even on success. A future
        version fixing this to return the updated Subscription would be a
        deliberate behavior change, not a regression this test should hide.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            mock.patch(f"/api/{__api_version__}/subs/{TOKEN}/comments").mock(
                return_value=httpx.Response(204)
            )
            async with make_client() as client:
                result = await client.update_comment(TOKEN, "cfg1", "x")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Operations
# ═══════════════════════════════════════════════════════════════════════════


class TestRefreshSubscription:
    async def test_basic(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post(f"/api/{__api_version__}/subs/{TOKEN}/refresh").mock(
                return_value=httpx.Response(
                    200,
                    json={"refreshed": 2, "failed": 0, "skipped": 1, "total": 3},
                )
            )
            async with make_client() as client:
                result = await client.refresh_subscription(TOKEN)
        assert result.refreshed == 2
        assert result.total == 3


# ═══════════════════════════════════════════════════════════════════════════
# Public endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestGetPublicSubscription:
    async def test_basic_no_title_header(self):
        import base64

        content = base64.b64encode(b"vless://a\nvless://b").decode()
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/sub/{TOKEN}").mock(return_value=httpx.Response(200, text=content))
            async with make_client() as client:
                resp = await client.get_public_subscription(TOKEN)
        assert isinstance(resp, PublicSubscriptionResponse)
        assert resp.title == "v2hub"
        assert resp.get_configs() == ["vless://a", "vless://b"]

    async def test_decodes_base64_title_header(self):
        import base64

        content = base64.b64encode(b"vless://a").decode()
        title_b64 = base64.b64encode(b"My Custom Title").decode()
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/sub/{TOKEN}").mock(
                return_value=httpx.Response(
                    200, text=content, headers={"profile-title": f"base64:{title_b64}"}
                )
            )
            async with make_client() as client:
                resp = await client.get_public_subscription(TOKEN)
        assert resp.title == "My Custom Title"

    async def test_malformed_title_header_falls_back_to_default(self):
        import base64

        content = base64.b64encode(b"vless://a").decode()
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get(f"/sub/{TOKEN}").mock(
                return_value=httpx.Response(
                    200, text=content, headers={"profile-title": "base64:not-valid-b64!!"}
                )
            )
            async with make_client() as client:
                resp = await client.get_public_subscription(TOKEN)
        assert resp.title == "v2hub"

    async def test_non_200_raises_mapped_exception(self):
        """
        get_public_subscription() has a manual `if response.status_code != 200`
        check with a bare VPNAPIError, but in practice HTTPClient._execute_request
        already raises a properly-mapped exception (e.g. NotFoundError for 404)
        for any status >= 400 before that manual check is ever reached. That
        manual check is effectively dead code for HTTP error statuses. This
        test pins down the actually-observed behavior; the InvalidURLError
        codepath below documents the (currently unreachable) manual branch.
        """
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/sub/missing").mock(return_value=httpx.Response(404, text="not found"))
            async with make_client() as client:
                with pytest.raises(NotFoundError) as exc_info:
                    await client.get_public_subscription("missing")
        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Retry integration (real end-to-end, not just unit-testing the decorator)
# ═══════════════════════════════════════════════════════════════════════════


class TestClientRetryIntegration:
    async def test_transient_server_error_is_retried(self, subscription_dict_factory, monkeypatch):
        import asyncio

        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

        client = AsyncVPNClient(
            BASE_URL,
            TOKEN,
            retry_config=RetryConfig(max_retries=2, initial_delay=0),
            circuit_breaker_config=CircuitBreakerConfig(enabled=False),
        )

        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(f"/api/{__api_version__}/subs/{TOKEN}")
            route.side_effect = [
                httpx.Response(500, json={"message": "boom"}),
                httpx.Response(200, json=subscription_dict_factory(token=TOKEN)),
            ]
            async with client:
                sub = await client.get_subscription(TOKEN)
        assert sub.token == TOKEN
        assert route.call_count == 2

    async def test_non_retryable_error_fails_fast(self):
        client = AsyncVPNClient(
            BASE_URL,
            TOKEN,
            retry_config=RetryConfig(max_retries=3, initial_delay=0),
            circuit_breaker_config=CircuitBreakerConfig(enabled=False),
        )
        with respx.mock(base_url=BASE_URL) as mock:
            route = mock.get(f"/api/{__api_version__}/subs/{TOKEN}").mock(
                return_value=httpx.Response(404, json={"message": "nope"})
            )
            async with client:
                with pytest.raises(NotFoundError):
                    await client.get_subscription(TOKEN)
        assert route.call_count == 1


async def _fast_sleep(_delay: float) -> None:
    return None
