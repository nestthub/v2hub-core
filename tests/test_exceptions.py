from __future__ import annotations

import pytest

from v2hub.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    CircularReferenceError,
    ConflictError,
    DuplicateNameError,
    ExternalFetchError,
    InvalidConfigError,
    InvalidURLError,
    NestingTooDeepError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    SourceNotFoundError,
    SubscriptionNotFoundError,
    TimeoutError,
    TooManyConfigsError,
    TooManySourcesError,
    TooManySubscriptionsError,
    ValidationError,
    VPNAPIError,
    get_exception_for_error,
    get_exception_for_exception,
    get_exception_for_status,
)

# ═══════════════════════════════════════════════════════════════════════════
# VPNAPIError base behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestVPNAPIErrorBase:
    def test_str_with_status_code(self):
        err = VPNAPIError("boom", status_code=500)
        assert str(err) == "[500] boom"

    def test_str_without_status_code(self):
        err = VPNAPIError("boom")
        assert str(err) == "boom"

    def test_repr(self):
        err = VPNAPIError("boom", status_code=500, retry_after=5)
        r = repr(err)
        assert "boom" in r
        assert "500" in r
        assert "5" in r

    def test_response_data_defaults_to_empty_dict(self):
        err = VPNAPIError("boom")
        assert err.response_data == {}

    def test_default_recovery_hint(self):
        err = VPNAPIError("boom")
        assert err.recovery_hint == "Contact API support if problem persists"

    def test_default_not_retryable(self):
        assert VPNAPIError("boom").is_retryable is False
        assert ValidationError("boom").is_retryable is False
        assert NotFoundError("boom").is_retryable is False
        assert ConflictError("boom").is_retryable is False


# ═══════════════════════════════════════════════════════════════════════════
# is_retryable
# ═══════════════════════════════════════════════════════════════════════════


class TestIsRetryable:
    @pytest.mark.parametrize(
        "exc_cls",
        [TimeoutError, ServerError, ServiceUnavailableError, RateLimitError, NetworkError],
    )
    def test_retryable_types(self, exc_cls):
        assert exc_cls("boom").is_retryable is True

    @pytest.mark.parametrize(
        "exc_cls",
        [
            ValidationError,
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            ConflictError,
            InvalidURLError,
            SubscriptionNotFoundError,
            SourceNotFoundError,
            InvalidConfigError,
            DuplicateNameError,
            CircularReferenceError,
            NestingTooDeepError,
            TooManyConfigsError,
            TooManySourcesError,
            TooManySubscriptionsError,
            ExternalFetchError,
            CacheError,
        ],
    )
    def test_non_retryable_types(self, exc_cls):
        assert exc_cls("boom").is_retryable is False


# ═══════════════════════════════════════════════════════════════════════════
# recovery_hint overrides
# ═══════════════════════════════════════════════════════════════════════════


class TestRecoveryHints:
    def test_rate_limit_with_retry_after(self):
        err = RateLimitError("boom", retry_after=30)
        assert "30 seconds" in err.recovery_hint

    def test_rate_limit_without_retry_after(self):
        err = RateLimitError("boom")
        assert err.recovery_hint == "Rate limited - wait before retrying"

    def test_invalid_url_hint(self):
        err = InvalidURLError("boom")
        assert "internal/local" in err.recovery_hint

    def test_subscription_not_found_hint(self):
        err = SubscriptionNotFoundError("boom")
        assert "Subscription not found" in err.recovery_hint

    def test_source_not_found_hint(self):
        err = SourceNotFoundError("boom")
        assert "Source not found" in err.recovery_hint

    def test_generic_hint_via_class_map(self):
        assert "validation" in ValidationError("boom").recovery_hint.lower()
        assert "token" in AuthenticationError("boom").recovery_hint.lower()


# ═══════════════════════════════════════════════════════════════════════════
# get_exception_for_status
# ═══════════════════════════════════════════════════════════════════════════


class TestGetExceptionForStatus:
    @pytest.mark.parametrize(
        "status,expected_cls",
        [
            (400, ValidationError),
            (401, AuthenticationError),
            (403, AuthorizationError),
            (404, NotFoundError),
            (409, ConflictError),
            (422, ValidationError),
            (429, RateLimitError),
            (500, ServerError),
            (502, ServiceUnavailableError),
            (503, ServiceUnavailableError),
            (504, TimeoutError),
        ],
    )
    def test_known_status_codes(self, status, expected_cls):
        exc = get_exception_for_status(status, "msg")
        assert isinstance(exc, expected_cls)
        assert exc.status_code == status

    def test_unknown_status_code_falls_back_to_base(self):
        exc = get_exception_for_status(418, "teapot")
        assert type(exc) is VPNAPIError
        assert exc.status_code == 418

    def test_error_type_in_body_overrides_status_code(self):
        # status says 404 (NotFoundError) but body says subscription_not_found
        # -> more specific SubscriptionNotFoundError should win
        exc = get_exception_for_status(
            404, "msg", response_data={"error": "subscription_not_found"}
        )
        assert isinstance(exc, SubscriptionNotFoundError)

    def test_error_type_case_insensitive(self):
        exc = get_exception_for_status(
            400, "msg", response_data={"error": "VALIDATION_ERROR"}
        )
        assert isinstance(exc, ValidationError)

    def test_message_extracted_from_body_message_field(self):
        exc = get_exception_for_status(
            400, "fallback", response_data={"message": "specific problem"}
        )
        assert exc.message == "specific problem"

    def test_message_extracted_from_detail_string(self):
        exc = get_exception_for_status(
            400, "fallback", response_data={"detail": "detail problem"}
        )
        assert exc.message == "detail problem"

    def test_message_extracted_from_nested_detail_dict(self):
        exc = get_exception_for_status(
            400,
            "fallback",
            response_data={"detail": {"message": "nested problem"}},
        )
        assert exc.message == "nested problem"

    def test_message_extracted_from_errors_list_of_strings(self):
        exc = get_exception_for_status(
            400, "fallback", response_data={"errors": ["first error", "second"]}
        )
        assert exc.message == "first error"

    def test_message_extracted_from_errors_list_of_dicts(self):
        exc = get_exception_for_status(
            400,
            "fallback",
            response_data={"errors": [{"message": "dict error"}]},
        )
        assert exc.message == "dict error"

    def test_message_falls_back_when_body_has_nothing_useful(self):
        exc = get_exception_for_status(400, "fallback", response_data={})
        assert exc.message == "fallback"

    def test_retry_after_extracted_as_int(self):
        exc = get_exception_for_status(
            429, "msg", response_data={"retry_after": 42}
        )
        assert exc.retry_after == 42

    def test_retry_after_extracted_from_numeric_string(self):
        exc = get_exception_for_status(
            429, "msg", response_data={"retry_after": "17"}
        )
        assert exc.retry_after == 17

    def test_retry_after_missing_is_none(self):
        exc = get_exception_for_status(429, "msg", response_data={})
        assert exc.retry_after is None

    def test_unknown_error_type_falls_back_to_status_map(self):
        exc = get_exception_for_status(
            404, "msg", response_data={"error": "some_unmapped_type"}
        )
        assert isinstance(exc, NotFoundError)
        assert not isinstance(exc, SubscriptionNotFoundError)


# ═══════════════════════════════════════════════════════════════════════════
# get_exception_for_error
# ═══════════════════════════════════════════════════════════════════════════


class TestGetExceptionForError:
    def test_error_type_without_status_code(self):
        exc = get_exception_for_error(
            "msg", response_data={"error": "not_found"}
        )
        assert isinstance(exc, NotFoundError)
        assert exc.status_code is None

    def test_falls_back_to_status_code_when_no_error_type_match(self):
        exc = get_exception_for_error(
            "msg", response_data={}, status_code=500
        )
        assert isinstance(exc, ServerError)

    def test_falls_back_to_base_vpnapi_error(self):
        exc = get_exception_for_error("plain message")
        assert type(exc) is VPNAPIError
        assert exc.message == "plain message"


# ═══════════════════════════════════════════════════════════════════════════
# get_exception_for_exception
# ═══════════════════════════════════════════════════════════════════════════


class TestGetExceptionForException:
    def test_timeout_like_exception(self):
        class SomeTimeoutException(Exception):
            pass

        exc = get_exception_for_exception(SomeTimeoutException("slow"))
        assert isinstance(exc, TimeoutError)

    @pytest.mark.parametrize(
        "cls_name",
        ["ConnectionError", "NetworkError", "DNSError", "SSLError", "ProxyError"],
    )
    def test_network_like_exceptions(self, cls_name):
        exc_type = type(cls_name, (Exception,), {})
        exc = get_exception_for_exception(exc_type("net down"))
        assert isinstance(exc, NetworkError)

    def test_unrecognized_exception_wraps_as_base(self):
        exc = get_exception_for_exception(ValueError("weird"))
        assert type(exc) is VPNAPIError
        assert "weird" in exc.message

    def test_custom_message_override(self):
        exc = get_exception_for_exception(ValueError("weird"), message="custom")
        assert exc.message == "custom"
