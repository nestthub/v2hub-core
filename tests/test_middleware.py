from __future__ import annotations

import logging

import httpx
import pytest
import respx

from v2hub.http.client import HTTPClient
from v2hub.http.middleware import LoggingMiddleware, MetricsMiddleware, RetryMiddleware

BASE_URL = "https://api.example.com"


class TestLoggingMiddleware:
    async def test_logs_successful_request_and_returns_response(self, caplog):
        caplog.set_level(logging.DEBUG, logger="v2hub.http.middleware")
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
            client = HTTPClient(base_url=BASE_URL, middleware=[LoggingMiddleware()])
            resp = await client.get("/ping")
            await client.close()

        assert resp.status_code == 200
        assert any("→ GET" in r.message for r in caplog.records)
        assert any("← 200 GET" in r.message for r in caplog.records)

    async def test_default_log_level_is_debug(self):
        middleware = LoggingMiddleware()
        assert middleware.log_level == logging.DEBUG

    async def test_custom_log_level(self):
        middleware = LoggingMiddleware(log_level=logging.INFO)
        assert middleware.log_level == logging.INFO

    async def test_logs_error_and_reraises(self, caplog):
        caplog.set_level(logging.DEBUG, logger="v2hub.http.middleware")
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/boom").mock(side_effect=httpx.ConnectError("boom"))
            client = HTTPClient(base_url=BASE_URL, middleware=[LoggingMiddleware()])
            with pytest.raises(Exception):  # noqa: B017 - NetworkError wraps ConnectError
                await client.get("/boom")
            await client.close()

        assert any("failed" in r.message for r in caplog.records)


class TestMetricsMiddleware:
    async def test_tracks_successful_requests(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
            middleware = MetricsMiddleware()
            client = HTTPClient(base_url=BASE_URL, middleware=[middleware])
            await client.get("/ping")
            await client.get("/ping")
            await client.close()

        assert middleware.request_count == 2
        assert middleware.error_count == 0
        assert middleware.total_duration >= 0.0
        assert middleware.average_duration >= 0.0
        metrics = middleware.get_metrics()
        assert metrics["request_count"] == 2
        assert metrics["error_count"] == 0
        assert metrics["error_rate"] == 0.0

    async def test_tracks_failed_requests(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/boom").mock(side_effect=httpx.ConnectError("boom"))
            middleware = MetricsMiddleware()
            client = HTTPClient(base_url=BASE_URL, middleware=[middleware])
            with pytest.raises(Exception):  # noqa: B017
                await client.get("/boom")
            await client.close()

        assert middleware.request_count == 1
        assert middleware.error_count == 1
        assert middleware.error_rate == 1.0

    def test_average_duration_zero_when_no_requests(self):
        middleware = MetricsMiddleware()
        assert middleware.average_duration == 0.0

    def test_error_rate_zero_when_no_requests(self):
        middleware = MetricsMiddleware()
        assert middleware.error_rate == 0.0

    def test_get_metrics_initial_state(self):
        middleware = MetricsMiddleware()
        metrics = middleware.get_metrics()
        assert metrics == {
            "request_count": 0,
            "error_count": 0,
            "error_rate": 0.0,
            "total_duration": 0.0,
            "average_duration": 0.0,
        }


class TestRetryMiddleware:
    async def test_passes_through_response(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
            client = HTTPClient(base_url=BASE_URL, middleware=[RetryMiddleware()])
            resp = await client.get("/ping")
            await client.close()

        assert resp.status_code == 200


class TestMiddlewareChaining:
    async def test_multiple_middleware_all_run(self):
        with respx.mock(base_url=BASE_URL) as mock:
            mock.get("/ping").mock(return_value=httpx.Response(200, json={"ok": True}))
            metrics = MetricsMiddleware()
            client = HTTPClient(
                base_url=BASE_URL,
                middleware=[LoggingMiddleware(), metrics, RetryMiddleware()],
            )
            resp = await client.get("/ping")
            await client.close()

        assert resp.status_code == 200
        assert metrics.request_count == 1
