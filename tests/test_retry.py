from __future__ import annotations

import asyncio

import pytest

from v2hub.core.exceptions import (
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from v2hub.core.retry import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryConfig,
    with_async_retry,
    with_retry,
)

# ═══════════════════════════════════════════════════════════════════════════
# RetryConfig.calculate_delay
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryConfigCalculateDelay:
    def test_exponential_growth_without_jitter(self):
        cfg = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False, max_delay=1000)
        assert cfg.calculate_delay(0) == 1.0
        assert cfg.calculate_delay(1) == 2.0
        assert cfg.calculate_delay(2) == 4.0
        assert cfg.calculate_delay(3) == 8.0

    def test_capped_at_max_delay(self):
        cfg = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False, max_delay=5.0)
        assert cfg.calculate_delay(10) == 5.0

    def test_jitter_stays_within_range(self):
        cfg = RetryConfig(initial_delay=10.0, exponential_base=1.0, jitter=True, max_delay=1000)
        for _ in range(50):
            delay = cfg.calculate_delay(0)
            # base delay is 10.0, jitter is +/-25% -> [7.5, 12.5]
            assert 7.5 <= delay <= 12.5

    def test_delay_never_negative(self):
        cfg = RetryConfig(initial_delay=0.0, jitter=True)
        assert cfg.calculate_delay(0) >= 0.0

    def test_default_retryable_exceptions(self):
        cfg = RetryConfig()
        from v2hub.core.exceptions import (
            RateLimitError as RLE,
        )
        from v2hub.core.exceptions import (
            ServerError as SE,
        )
        from v2hub.core.exceptions import (
            ServiceUnavailableError as SUE,
        )
        from v2hub.core.exceptions import (
            TimeoutError as TOE,
        )

        assert cfg.retryable_exceptions == (TOE, SE, SUE, RLE)


# ═══════════════════════════════════════════════════════════════════════════
# with_async_retry
# ═══════════════════════════════════════════════════════════════════════════


class TestWithAsyncRetry:
    async def test_succeeds_without_retry(self):
        calls = []

        @with_async_retry(RetryConfig(max_retries=3, initial_delay=0))
        async def fn():
            calls.append(1)
            return "ok"

        result = await fn()
        assert result == "ok"
        assert len(calls) == 1

    async def test_retries_on_retryable_exception_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)
        calls = {"n": 0}

        @with_async_retry(RetryConfig(max_retries=3, initial_delay=0))
        async def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ServerError("boom")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert calls["n"] == 3

    async def test_exhausts_retries_and_raises_last_exception(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", _fast_sleep)
        calls = {"n": 0}

        @with_async_retry(RetryConfig(max_retries=2, initial_delay=0))
        async def fn():
            calls["n"] += 1
            raise ServerError("always fails")

        with pytest.raises(ServerError):
            await fn()
        # initial attempt + 2 retries = 3 calls
        assert calls["n"] == 3

    async def test_non_retryable_exception_raised_immediately(self):
        calls = {"n": 0}

        @with_async_retry(RetryConfig(max_retries=3, initial_delay=0))
        async def fn():
            calls["n"] += 1
            raise ValidationError("bad input")

        with pytest.raises(ValidationError):
            await fn()
        assert calls["n"] == 1

    async def test_rate_limit_retry_after_used_as_delay(self, monkeypatch):
        recorded_delays = []

        async def fake_sleep(delay):
            recorded_delays.append(delay)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        calls = {"n": 0}

        @with_async_retry(RetryConfig(max_retries=1, initial_delay=0))
        async def fn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RateLimitError("slow down", retry_after=7)
            return "ok"

        result = await fn()
        assert result == "ok"
        assert recorded_delays == [7]

    async def test_preserves_function_metadata(self):
        @with_async_retry()
        async def my_function():
            """docstring"""
            return 1

        assert my_function.__name__ == "my_function"

    async def test_passes_args_and_kwargs_through(self):
        @with_async_retry(RetryConfig(max_retries=0))
        async def fn(a, b, c=None):
            return (a, b, c)

        result = await fn(1, 2, c=3)
        assert result == (1, 2, 3)


async def _fast_sleep(_delay: float) -> None:
    return None


# ═══════════════════════════════════════════════════════════════════════════
# with_retry (sync)
# ═══════════════════════════════════════════════════════════════════════════


class TestWithRetry:
    def test_succeeds_without_retry(self):
        calls = []

        @with_retry(RetryConfig(max_retries=3, initial_delay=0))
        def fn():
            calls.append(1)
            return "ok"

        assert fn() == "ok"
        assert len(calls) == 1

    def test_retries_then_succeeds(self, monkeypatch):
        import time

        monkeypatch.setattr(time, "sleep", lambda _s: None)
        calls = {"n": 0}

        @with_retry(RetryConfig(max_retries=3, initial_delay=0))
        def fn():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ServerError("boom")
            return "ok"

        assert fn() == "ok"
        assert calls["n"] == 2

    def test_exhausts_and_raises(self, monkeypatch):
        import time

        monkeypatch.setattr(time, "sleep", lambda _s: None)

        @with_retry(RetryConfig(max_retries=1, initial_delay=0))
        def fn():
            raise ServerError("always")

        with pytest.raises(ServerError):
            fn()

    def test_non_retryable_raised_immediately(self):
        calls = {"n": 0}

        @with_retry(RetryConfig(max_retries=3, initial_delay=0))
        def fn():
            calls["n"] += 1
            raise NotFoundError("nope")

        with pytest.raises(NotFoundError):
            fn()
        assert calls["n"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# CircuitBreaker
# ═══════════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    async def test_starts_closed(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        assert cb.state == CircuitState.CLOSED

    async def test_successful_calls_keep_circuit_closed(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

        async def ok():
            return "ok"

        for _ in range(5):
            result = await cb.call(ok)
            assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, timeout=1000))

        async def fail():
            raise ServerError("boom")

        for _ in range(3):
            with pytest.raises(ServerError):
                await cb.call(fail)

        assert cb.state == CircuitState.OPEN

    async def test_open_circuit_rejects_calls_without_invoking_func(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, timeout=1000))
        calls = {"n": 0}

        async def fail():
            calls["n"] += 1
            raise ServerError("boom")

        with pytest.raises(ServerError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

        from v2hub.core.exceptions import ServiceUnavailableError

        with pytest.raises(ServiceUnavailableError):
            await cb.call(fail)
        # second call should have been rejected by the breaker, not executed
        assert calls["n"] == 1

    async def test_transitions_to_half_open_after_timeout(self, monkeypatch):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, timeout=0))

        async def fail():
            raise ServerError("boom")

        with pytest.raises(ServerError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

        async def ok():
            return "ok"

        # timeout=0 means _should_attempt_reset is True immediately
        result = await cb.call(ok)
        assert result == "ok"
        # one success with success_threshold=2 (default) keeps it half-open
        assert cb.state == CircuitState.HALF_OPEN

    async def test_closes_after_success_threshold_in_half_open(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, success_threshold=2, timeout=0)
        )

        async def fail():
            raise ServerError("boom")

        async def ok():
            return "ok"

        with pytest.raises(ServerError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

        await cb.call(ok)
        assert cb.state == CircuitState.HALF_OPEN
        await cb.call(ok)
        assert cb.state == CircuitState.CLOSED

    async def test_failure_in_half_open_reopens_circuit(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, timeout=0))

        async def fail():
            raise ServerError("boom")

        with pytest.raises(ServerError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

        with pytest.raises(ServerError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

    async def test_disabled_breaker_always_calls_through(self):
        cb = CircuitBreaker(CircuitBreakerConfig(enabled=False, failure_threshold=1))

        async def fail():
            raise ServerError("boom")

        for _ in range(5):
            with pytest.raises(ServerError):
                await cb.call(fail)
        # disabled breaker never tracks/opens
        assert cb.state == CircuitState.CLOSED
