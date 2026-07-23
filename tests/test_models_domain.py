from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError as PydanticValidationError

from v2hub.models.enums import SourceType
from v2hub.models.public import PublicSubscriptionResponse
from v2hub.models.responses import ErrorResponse, RefreshSubscriptionResponse
from v2hub.models.sources import Source
from v2hub.models.subscriptions import Subscription, SubscriptionListItem

# ═══════════════════════════════════════════════════════════════════════════
# SourceType
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceType:
    def test_values(self):
        assert SourceType.CONFIG == "config"
        assert SourceType.EXTERNAL_URL == "external_url"
        assert SourceType.INTERNAL_TOKEN == "internal_token"

    def test_str(self):
        assert str(SourceType.CONFIG) == "config"

    def test_from_string_value(self):
        assert SourceType("config") is SourceType.CONFIG


# ═══════════════════════════════════════════════════════════════════════════
# Source
# ═══════════════════════════════════════════════════════════════════════════


class TestSource:
    def test_basic(self, source_dict_factory):
        s = Source(**source_dict_factory())
        assert s.id == "src1"
        # use_enum_values=True on BaseModelConfig -> stored as plain str
        assert s.source_type == "config"
        assert s.data == "vless://uuid@server:443#Server1"
        assert s.order_index == 0

    def test_data_stripped(self, source_dict_factory):
        d = source_dict_factory(data="  vless://a  ")
        s = Source(**d)
        assert s.data == "vless://a"

    def test_empty_data_rejected(self, source_dict_factory):
        d = source_dict_factory(data="   ")
        with pytest.raises(PydanticValidationError):
            Source(**d)

    def test_negative_order_index_rejected(self, source_dict_factory):
        d = source_dict_factory(order_index=-1)
        with pytest.raises(PydanticValidationError):
            Source(**d)

    def test_missing_required_field_rejected(self, source_dict_factory):
        d = source_dict_factory()
        del d["id"]
        with pytest.raises(PydanticValidationError):
            Source(**d)

    def test_invalid_source_type_rejected(self, source_dict_factory):
        d = source_dict_factory(source_type="not_a_real_type")
        with pytest.raises(PydanticValidationError):
            Source(**d)

    def test_is_hidden_and_max_depth_defaults_if_present(self, source_dict_factory):
        """
        Source may or may not carry is_hidden/max_depth depending on the
        library version. If present, they must default to non-breaking
        values (not hidden, some sane depth) so that responses for
        existing/older sources -- which never set these explicitly --
        behave the same as before the fields were added. If the fields
        aren't present at all, there's nothing to check here and the test
        passes trivially; this is intentionally forward-compatible rather
        than asserting a specific version's shape.
        """
        s = Source(**source_dict_factory())
        if hasattr(s, "is_hidden"):
            assert s.is_hidden is False, (
                "A Source with no is_hidden specified in the API response "
                "must default to visible (False), or existing sources "
                "would silently disappear from resolved output."
            )
        if hasattr(s, "max_depth"):
            assert isinstance(s.max_depth, int) and s.max_depth >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Subscription / SubscriptionListItem
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscription:
    def test_basic(self, subscription_dict_factory):
        sub = Subscription(**subscription_dict_factory())
        assert sub.token == "sub-token-abc"
        assert sub.name == "My VPN"
        assert len(sub.sources) == 1
        assert isinstance(sub.sources[0], Source)

    def test_empty_sources_default(self, subscription_dict_factory):
        d = subscription_dict_factory(sources=[], sources_count=0)
        sub = Subscription(**d)
        assert sub.sources == []

    def test_sources_count_less_than_actual_does_not_raise(
        self, subscription_dict_factory, source_dict_factory
    ):
        # sources_count is a soft sanity check only; a mismatch is tolerated.
        d = subscription_dict_factory(
            sources=[source_dict_factory(id="a"), source_dict_factory(id="b")],
            sources_count=0,
        )
        sub = Subscription(**d)
        assert sub.sources_count == 0
        assert len(sub.sources) == 2

    def test_negative_sources_count_rejected(self, subscription_dict_factory):
        d = subscription_dict_factory(sources_count=-1)
        with pytest.raises(PydanticValidationError):
            Subscription(**d)

    def test_name_max_length(self, subscription_dict_factory):
        d = subscription_dict_factory(name="x" * 65)
        with pytest.raises(PydanticValidationError):
            Subscription(**d)

    def test_subscription_list_item_is_subscription_subclass(self, subscription_dict_factory):
        item = SubscriptionListItem(**subscription_dict_factory())
        assert isinstance(item, Subscription)


# ═══════════════════════════════════════════════════════════════════════════
# PublicSubscriptionResponse
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicSubscriptionResponse:
    def test_default_title(self):
        content = base64.b64encode(b"vless://a\nvless://b").decode()
        resp = PublicSubscriptionResponse(content=content)
        assert resp.title == "v2hub"

    def test_decode(self):
        raw = "vless://a\nvless://b\n"
        content = base64.b64encode(raw.encode()).decode()
        resp = PublicSubscriptionResponse(content=content)
        assert resp.decode() == raw

    def test_decode_invalid_base64_raises_value_error(self):
        resp = PublicSubscriptionResponse.model_construct(content="not-valid-base64!!!")
        with pytest.raises(ValueError):
            resp.decode()

    def test_get_configs_splits_and_strips_lines(self):
        raw = "vless://a\n\n  vless://b  \nvless://c"
        content = base64.b64encode(raw.encode()).decode()
        resp = PublicSubscriptionResponse(content=content)
        assert resp.get_configs() == ["vless://a", "vless://b", "vless://c"]

    def test_config_count_property(self):
        raw = "vless://a\nvless://b"
        content = base64.b64encode(raw.encode()).decode()
        resp = PublicSubscriptionResponse(content=content)
        assert resp.config_count == 2

    def test_config_count_empty_content(self):
        content = base64.b64encode(b"").decode()
        resp = PublicSubscriptionResponse(content=content)
        assert resp.config_count == 0

    def test_content_required(self):
        with pytest.raises(PydanticValidationError):
            PublicSubscriptionResponse()


# ═══════════════════════════════════════════════════════════════════════════
# RefreshSubscriptionResponse / ErrorResponse
# ═══════════════════════════════════════════════════════════════════════════


class TestRefreshSubscriptionResponse:
    def test_defaults(self):
        resp = RefreshSubscriptionResponse()
        assert resp.refreshed == 0
        assert resp.failed == 0
        assert resp.skipped == 0
        assert resp.total == 0
        assert resp.message is None
        assert resp.errors is None

    def test_full(self):
        resp = RefreshSubscriptionResponse(
            refreshed=3,
            failed=1,
            skipped=0,
            total=4,
            message="done",
            errors=["https://x: timeout"],
        )
        assert resp.refreshed == 3
        assert resp.errors == ["https://x: timeout"]


class TestErrorResponse:
    def test_basic(self):
        err = ErrorResponse(error="not_found", message="Subscription not found")
        assert err.error == "not_found"
        assert err.details is None

    def test_requires_error_and_message(self):
        with pytest.raises(PydanticValidationError):
            ErrorResponse(message="only message")
        with pytest.raises(PydanticValidationError):
            ErrorResponse(error="only_error")

    def test_details_optional_dict(self):
        err = ErrorResponse(error="validation_error", message="bad", details={"field": "name"})
        assert err.details == {"field": "name"}
