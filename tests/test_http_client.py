from __future__ import annotations

import httpx
import pytest
import respx

from v2hub.core.exceptions import NetworkError, NotFoundError, TimeoutError, ValidationError
from v2hub.http.client import HTTPClient, Middleware, RequestContext

BASE_URL = "https://api.example.com"


class TestHTTPClientLifecycle:
    async def test_connect_and_close(self):
        client = HTTPClient(base_url=BASE_URL)
        assert client._client is None
        await client.connect()
        assert client._client is not None
        await client.close()
        assert client._client is None

    async def test_context_manager(self):
        async with HTTPClient(base_url=BASE_URL) as client:
            assert client._client is not None

    async def test_base_url_trailing_slash_stripped(self):
        client = HTTPClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    async def test_auto_connects_on_first_request(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
            client = HTTPClient(base_url=BASE_URL)
            assert client._client is None
            resp = await client.get("/ping")
            assert resp.status_code == 200
            await client.close()


class TestHTTPClientSuccessResponses:
    async def test_get(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/thing").mock(return_value=httpx.Response(200, json={"a": 1}))
            async with HTTPClient(base_url=BASE_URL) as client:
                resp = await client.get("/thing")
                assert resp.json() == {"a": 1}

    async def test_post(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/thing").mock(return_value=httpx.Response(201, json={"created": True}))
            async with HTTPClient(base_url=BASE_URL) as client:
                resp = await client.post("/thing", json={"x": 1})
                assert resp.status_code == 201

    async def test_put(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.put("/thing").mock(return_value=httpx.Response(200, json={}))
            async with HTTPClient(base_url=BASE_URL) as client:
                resp = await client.put("/thing", json={})
                assert resp.status_code == 200

    async def test_patch(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.patch("/thing").mock(return_value=httpx.Response(200, json={}))
            async with HTTPClient(base_url=BASE_URL) as client:
                resp = await client.patch("/thing", json={})
                assert resp.status_code == 200

    async def test_delete(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.delete("/thing").mock(return_value=httpx.Response(204))
            async with HTTPClient(base_url=BASE_URL) as client:
                resp = await client.delete("/thing")
                assert resp.status_code == 204


class TestHTTPClientErrorMapping:
    async def test_4xx_raises_mapped_exception(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/missing").mock(
                return_value=httpx.Response(404, json={"message": "not here"})
            )
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(NotFoundError) as exc_info:
                    await client.get("/missing")
                assert exc_info.value.message == "not here"

    async def test_400_raises_validation_error(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.post("/thing").mock(
                return_value=httpx.Response(400, json={"message": "bad input"})
            )
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(ValidationError):
                    await client.post("/thing", json={})

    async def test_non_json_error_body_uses_text(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/broken").mock(return_value=httpx.Response(500, text="internal error"))
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.get("/broken")
                assert "internal error" in str(exc_info.value)

    async def test_empty_error_body_uses_status_fallback_message(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/broken").mock(return_value=httpx.Response(500, text=""))
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.get("/broken")
                assert "500" in str(exc_info.value)

    async def test_timeout_exception_mapped(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/slow").mock(side_effect=httpx.TimeoutException("too slow"))
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(TimeoutError):
                    await client.get("/slow")

    async def test_network_exception_mapped(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/down").mock(side_effect=httpx.ConnectError("refused"))
            async with HTTPClient(base_url=BASE_URL) as client:
                with pytest.raises(NetworkError):
                    await client.get("/down")


class TestHTTPClientMiddleware:
    async def test_middleware_is_invoked(self):
        calls = []

        class RecordingMiddleware(Middleware):
            async def __call__(self, context: RequestContext, call_next):
                calls.append(("before", context.method, context.url))
                response = await call_next()
                calls.append(("after", response.status_code))
                return response

        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/thing").mock(return_value=httpx.Response(200, json={}))
            client = HTTPClient(base_url=BASE_URL, middleware=[RecordingMiddleware()])
            async with client:
                await client.get("/thing")

        assert calls[0][0] == "before"
        assert calls[0][1] == "GET"
        assert calls[1] == ("after", 200)

    async def test_middleware_chain_order(self):
        """Middleware should run in list order (first middleware outermost)."""
        order = []

        class TaggedMiddleware(Middleware):
            def __init__(self, tag):
                self.tag = tag

            async def __call__(self, context, call_next):
                order.append(f"{self.tag}-before")
                result = await call_next()
                order.append(f"{self.tag}-after")
                return result

        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/thing").mock(return_value=httpx.Response(200, json={}))
            client = HTTPClient(
                base_url=BASE_URL,
                middleware=[TaggedMiddleware("A"), TaggedMiddleware("B")],
            )
            async with client:
                await client.get("/thing")

        assert order == ["A-before", "B-before", "B-after", "A-after"]

    async def test_middleware_can_short_circuit(self):
        """A middleware that doesn't call call_next() should still work."""

        class ShortCircuitMiddleware(Middleware):
            async def __call__(self, context, call_next):
                return httpx.Response(200, json={"short_circuited": True})

        client = HTTPClient(base_url=BASE_URL, middleware=[ShortCircuitMiddleware()])
        async with client:
            resp = await client.get("/never-hits-network")
        assert resp.json() == {"short_circuited": True}


class TestRequestContext:
    def test_defaults(self):
        ctx = RequestContext(method="GET", url="https://x/y")
        assert ctx.method == "GET"
        assert ctx.url == "https://x/y"
        assert ctx.retries == 0
        assert ctx.metadata == {}

    def test_custom_metadata(self):
        ctx = RequestContext(method="POST", url="https://x", metadata={"k": "v"})
        assert ctx.metadata == {"k": "v"}
