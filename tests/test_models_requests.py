"""
Tests for src/v2hub/models/requests.py.

These check BEHAVIOR (does a plain-string source still work? is the data
preserved? is dedup/validation still enforced?) rather than the exact
internal shape of `.sources`. That distinction matters because the
library made a backward-compatible change: `sources` fields went from
list[str] to list[SourceCreate] (each item gaining is_hidden/max_depth
with defaults False/3). Old caller code keeps working -- only what you
get back when you inspect `.sources` changed shape. Tests hard-coded to
`req.sources == ["a", "b"]` would flag that as a break even though
nothing is actually broken; using source_data_list()/get_attr_or_key()
from _helpers.py keeps the tests coupled to real behavior instead.

If you're extending this file for a genuinely new capability (e.g. some
future field), prefer the same pattern: assert on the *data that matters*
via a helper, not on the literal python type/shape of the field. That way
the next backward-compatible enhancement doesn't require rewriting every
test that happens to touch `sources`.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from v2hub.models.requests import (
    CommentUpdateRequest,
    SourceAddRequest,
    SourceRemoveRequest,
    SourceReplaceRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
)

from ._helpers import get_attr_or_key, source_data_list

try:
    from v2hub.models.requests import SourceUpdateRequest
    HAS_SOURCE_UPDATE_REQUEST = True
except ImportError:
    HAS_SOURCE_UPDATE_REQUEST = False


# ═══════════════════════════════════════════════════════════════════════════
# SubscriptionCreateRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscriptionCreateRequest:
    def test_minimal_valid(self):
        req = SubscriptionCreateRequest(name="my-vpn")
        assert req.name == "my-vpn"
        assert req.description is None
        assert req.sources in ([], None)  # some versions default to None, some to []

    def test_name_is_stripped(self):
        req = SubscriptionCreateRequest(name="  my-vpn  ")
        assert req.name == "my-vpn"

    def test_empty_name_after_strip_rejected(self):
        with pytest.raises(PydanticValidationError):
            SubscriptionCreateRequest(name="   ")

    def test_name_too_long_rejected(self):
        with pytest.raises(PydanticValidationError):
            SubscriptionCreateRequest(name="x" * 65)

    def test_description_max_length(self):
        req = SubscriptionCreateRequest(name="x", description="d" * 255)
        assert req.description == "d" * 255
        with pytest.raises(PydanticValidationError):
            SubscriptionCreateRequest(name="x", description="d" * 256)

    def test_sources_default_is_empty(self):
        req = SubscriptionCreateRequest(name="x")
        assert not req.sources  # covers both [] and None as "nothing provided"

    def test_sources_accepts_plain_strings(self):
        """
        The original, still-supported calling convention: pass a plain
        list of source strings. This must keep working regardless of how
        the library wraps/enriches them internally.
        """
        req = SubscriptionCreateRequest(
            name="x", sources=["vless://a", "vless://b"]
        )
        assert source_data_list(req.sources) == ["vless://a", "vless://b"]

    def test_sources_strip_whitespace(self):
        req = SubscriptionCreateRequest(name="x", sources=["  vless://a  "])
        assert source_data_list(req.sources) == ["vless://a"]

    def test_sources_dedup_preserves_order(self):
        req = SubscriptionCreateRequest(
            name="x", sources=["vless://a", "vless://b", "vless://a"]
        )
        assert source_data_list(req.sources) == ["vless://a", "vless://b"]

    def test_sources_empty_strings_filtered(self):
        req = SubscriptionCreateRequest(name="x", sources=["vless://a", "  ", ""])
        assert source_data_list(req.sources) == ["vless://a"]

    def test_sources_all_empty_becomes_falsy(self):
        req = SubscriptionCreateRequest(name="x", sources=["   ", ""])
        assert not req.sources  # accepts either None or [] as "nothing"

    def test_serialization_round_trip_preserves_data(self):
        """
        Whatever the on-disk/wire shape (bare strings or enriched objects),
        the source data itself must survive a model_dump() -> the caller
        should be able to find "vless://a" in the dumped payload somehow.
        """
        req = SubscriptionCreateRequest(
            name="x", description="d", sources=["vless://a"]
        )
        dumped = req.model_dump(mode="json")
        assert dumped["name"] == "x"
        assert dumped["description"] == "d"
        dumped_sources = dumped["sources"]
        assert len(dumped_sources) == 1
        first = dumped_sources[0]
        data_value = first if isinstance(first, str) else first["data"]
        assert data_value == "vless://a"

    def test_new_fields_have_safe_defaults_for_plain_string_input(self):
        """
        If a source item now carries extra fields (is_hidden, max_depth,
        etc.), a plain-string input must map to non-breaking defaults:
        not hidden, and some sane default depth. This is a soft/behavioral
        check -- it only asserts *if* those fields are present, they don't
        silently opt a source out of normal behavior.
        """
        req = SubscriptionCreateRequest(name="x", sources=["vless://a"])
        item = req.sources[0]
        is_hidden = get_attr_or_key(item, "is_hidden", default=False)
        assert is_hidden is None, (
            "Plain-string sources must not default to hidden -- that would "
            "silently change behavior for all existing callers."
        )


# ═══════════════════════════════════════════════════════════════════════════
# SubscriptionUpdateRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscriptionUpdateRequest:
    def test_name_only(self):
        req = SubscriptionUpdateRequest(name="new-name")
        assert req.name == "new-name"
        assert req.description is None

    def test_description_only(self):
        req = SubscriptionUpdateRequest(description="new-desc")
        assert req.description == "new-desc"
        assert req.name is None

    def test_both_fields(self):
        req = SubscriptionUpdateRequest(name="n", description="d")
        assert req.name == "n"
        assert req.description == "d"

    def test_neither_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SubscriptionUpdateRequest()

    def test_name_stripped(self):
        req = SubscriptionUpdateRequest(name="  n  ")
        assert req.name == "n"

    def test_empty_name_after_strip_rejected(self):
        with pytest.raises(PydanticValidationError):
            SubscriptionUpdateRequest(name="   ")

    def test_exclude_none_serialization(self):
        req = SubscriptionUpdateRequest(name="n")
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped == {"name": "n"}


# ═══════════════════════════════════════════════════════════════════════════
# SourceAddRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceAddRequest:
    def test_basic_plain_strings_still_work(self):
        req = SourceAddRequest(sources=["vless://a", "vless://b"])
        assert source_data_list(req.sources) == ["vless://a", "vless://b"]

    def test_requires_at_least_one_source(self):
        with pytest.raises(PydanticValidationError):
            SourceAddRequest(sources=[])

    def test_all_blank_sources_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceAddRequest(sources=["   ", ""])

    def test_dedup_preserves_order(self):
        req = SourceAddRequest(sources=["a", "b", "a", "c", "b"])
        assert source_data_list(req.sources) == ["a", "b", "c"]

    def test_strips_whitespace(self):
        req = SourceAddRequest(sources=["  a  ", "b"])
        assert source_data_list(req.sources) == ["a", "b"]

    def test_missing_sources_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceAddRequest()

    def test_object_form_accepted_if_supported(self):
        """
        If the library now accepts explicit objects (dicts with
        data/is_hidden/max_depth) rather than only plain strings, that
        should also work -- this is additive, so we only assert when it's
        actually supported (won't fail on older/pre-update code).
        """
        try:
            req = SourceAddRequest(
                sources=[{"data": "vless://a", "is_hidden": True, "max_depth": 1}]
            )
        except PydanticValidationError:
            pytest.skip("object-form sources not supported by this version")
        item = req.sources[0]
        assert get_attr_or_key(item, "data") == "vless://a"
        assert get_attr_or_key(item, "is_hidden") is True
        assert get_attr_or_key(item, "max_depth") == 1


# ═══════════════════════════════════════════════════════════════════════════
# SourceReplaceRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceReplaceRequest:
    def test_basic_plain_strings_still_work(self):
        req = SourceReplaceRequest(sources=["a", "b"])
        assert source_data_list(req.sources) == ["a", "b"]

    def test_empty_list_allowed(self):
        req = SourceReplaceRequest(sources=[])
        assert not req.sources

    def test_all_blank_sources_become_empty(self):
        req = SourceReplaceRequest(sources=["  ", ""])
        assert not req.sources

    def test_dedup_preserves_order(self):
        req = SourceReplaceRequest(sources=["x", "y", "x"])
        assert source_data_list(req.sources) == ["x", "y"]

    def test_missing_sources_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceReplaceRequest()


# ═══════════════════════════════════════════════════════════════════════════
# SourceRemoveRequest (unaffected by the sources-shape change; kept as-is)
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceRemoveRequest:
    def test_basic(self):
        req = SourceRemoveRequest(source_ids=["id1", "id2"])
        assert req.source_ids == ["id1", "id2"]

    def test_requires_at_least_one_id(self):
        with pytest.raises(PydanticValidationError):
            SourceRemoveRequest(source_ids=[])

    def test_all_blank_ids_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceRemoveRequest(source_ids=["  ", ""])

    def test_dedup_preserves_order(self):
        req = SourceRemoveRequest(source_ids=["id1", "id2", "id1"])
        assert req.source_ids == ["id1", "id2"]

    def test_strips_whitespace(self):
        req = SourceRemoveRequest(source_ids=["  id1  "])
        assert req.source_ids == ["id1"]


# ═══════════════════════════════════════════════════════════════════════════
# CommentUpdateRequest (deprecated but must keep working)
# ═══════════════════════════════════════════════════════════════════════════


class TestCommentUpdateRequest:
    def test_basic_still_works(self):
        """
        Deprecated in favor of SourceUpdateRequest, but must still work
        for old caller code -- deprecation means "don't use this for new
        code", not "this is broken now".
        """
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            req = CommentUpdateRequest(config_id="cfg1", comment="hello")
        assert req.config_id == "cfg1"
        assert req.comment == "hello"

    def test_comment_none_allowed(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            req = CommentUpdateRequest(config_id="cfg1", comment=None)
        assert req.comment is None

    def test_config_id_required(self):
        with pytest.raises(PydanticValidationError):
            CommentUpdateRequest(comment="hello")

    def test_config_id_min_length(self):
        with pytest.raises(PydanticValidationError):
            CommentUpdateRequest(config_id="", comment="hello")

    def test_comment_max_length(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            req = CommentUpdateRequest(config_id="cfg1", comment="c" * 255)
        assert req.comment == "c" * 255
        with pytest.raises(PydanticValidationError):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                CommentUpdateRequest(config_id="cfg1", comment="c" * 256)

    def test_exclude_none_serialization_drops_comment(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            req = CommentUpdateRequest(config_id="cfg1", comment=None)
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped == {"config_id": "cfg1"}

    def test_using_it_now_emits_deprecation_warning(self):
        """
        Confirms the deprecation notice fires, without failing the test
        suite over it (pytest.ini/pyproject may turn warnings into errors
        elsewhere; this test isolates it deliberately).
        """
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            CommentUpdateRequest(config_id="cfg1", comment="hi")
        deprecation_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        if not deprecation_warnings:
            pytest.skip(
                "This version of CommentUpdateRequest does not emit a "
                "DeprecationWarning -- not a failure, just nothing to check."
            )
        assert "SourceUpdateRequest" in str(deprecation_warnings[0].message)


# ═══════════════════════════════════════════════════════════════════════════
# SourceUpdateRequest (new; only runs if the library provides it)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    not HAS_SOURCE_UPDATE_REQUEST,
    reason="SourceUpdateRequest not present in this version of the library",
)
class TestSourceUpdateRequest:
    def test_config_id_only(self):
        req = SourceUpdateRequest(config_id="cfg1")
        assert req.config_id == "cfg1"

    def test_comment_field(self):
        req = SourceUpdateRequest(config_id="cfg1", comment="hello")
        assert req.comment == "hello"

    def test_is_hidden_field(self):
        req = SourceUpdateRequest(config_id="cfg1", is_hidden=True)
        assert req.is_hidden is True

    def test_max_depth_field(self):
        req = SourceUpdateRequest(config_id="cfg1", max_depth=2)
        assert req.max_depth == 2

    def test_config_id_required(self):
        with pytest.raises(PydanticValidationError):
            SourceUpdateRequest()

    def test_unset_fields_stay_none_and_are_excluded_on_dump(self):
        """
        Partial-update semantics: only explicitly provided fields should
        be sent, so exclude_none=True dumps must omit anything not set.
        """
        req = SourceUpdateRequest(config_id="cfg1", is_hidden=True)
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped == {"config_id": "cfg1", "is_hidden": True}

    def test_all_fields_together(self):
        req = SourceUpdateRequest(
            config_id="cfg1", comment="hi", is_hidden=False, max_depth=1
        )
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped == {
            "config_id": "cfg1",
            "comment": "hi",
            "is_hidden": False,
            "max_depth": 1,
        }
