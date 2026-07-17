"""
Tests for src/v2hub/models/requests.py.

These pin down the CURRENT behavior of the request models (list[str]-based
sources, dedup rules, validation errors) so that a library update which
switches `sources` to an object-based shape (e.g. list[SourceCreate] with
is_hidden/max_depth) is forced to either preserve these semantics for
plain-string input or deliberately update this test suite.
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


# ═══════════════════════════════════════════════════════════════════════════
# SubscriptionCreateRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSubscriptionCreateRequest:
    def test_minimal_valid(self):
        req = SubscriptionCreateRequest(name="my-vpn")
        assert req.name == "my-vpn"
        assert req.description is None
        assert req.sources == []

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

    def test_sources_default_empty_list(self):
        req = SubscriptionCreateRequest(name="x")
        assert req.sources == []

    def test_sources_accepts_plain_strings(self):
        req = SubscriptionCreateRequest(
            name="x", sources=["vless://a", "vless://b"]
        )
        assert req.sources == ["vless://a", "vless://b"]

    def test_sources_strip_whitespace(self):
        req = SubscriptionCreateRequest(name="x", sources=["  vless://a  "])
        assert req.sources == ["vless://a"]

    def test_sources_dedup_preserves_order(self):
        req = SubscriptionCreateRequest(
            name="x", sources=["vless://a", "vless://b", "vless://a"]
        )
        assert req.sources == ["vless://a", "vless://b"]

    def test_sources_empty_strings_filtered(self):
        req = SubscriptionCreateRequest(name="x", sources=["vless://a", "  ", ""])
        assert req.sources == ["vless://a"]

    def test_sources_all_empty_becomes_none(self):
        # Current (pre-update) behavior: an all-empty/whitespace sources list
        # collapses to None rather than an empty list.
        req = SubscriptionCreateRequest(name="x", sources=["   ", ""])
        assert req.sources is None

    def test_serialization_round_trip(self):
        req = SubscriptionCreateRequest(
            name="x", description="d", sources=["vless://a"]
        )
        dumped = req.model_dump(mode="json")
        assert dumped == {
            "name": "x",
            "description": "d",
            "sources": ["vless://a"],
        }


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
    def test_basic(self):
        req = SourceAddRequest(sources=["vless://a", "vless://b"])
        assert req.sources == ["vless://a", "vless://b"]

    def test_requires_at_least_one_source(self):
        with pytest.raises(PydanticValidationError):
            SourceAddRequest(sources=[])

    def test_all_blank_sources_rejected(self):
        # After stripping, an all-blank list has nothing left, which raises
        # explicitly (unlike SubscriptionCreateRequest, which returns None).
        with pytest.raises(PydanticValidationError):
            SourceAddRequest(sources=["   ", ""])

    def test_dedup_preserves_order(self):
        req = SourceAddRequest(sources=["a", "b", "a", "c", "b"])
        assert req.sources == ["a", "b", "c"]

    def test_strips_whitespace(self):
        req = SourceAddRequest(sources=["  a  ", "b"])
        assert req.sources == ["a", "b"]

    def test_missing_sources_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceAddRequest()


# ═══════════════════════════════════════════════════════════════════════════
# SourceReplaceRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceReplaceRequest:
    def test_basic(self):
        req = SourceReplaceRequest(sources=["a", "b"])
        assert req.sources == ["a", "b"]

    def test_empty_list_allowed(self):
        # Unlike SourceAddRequest, an empty list is a valid "clear all" request.
        req = SourceReplaceRequest(sources=[])
        assert req.sources == []

    def test_all_blank_sources_become_empty_list(self):
        req = SourceReplaceRequest(sources=["  ", ""])
        assert req.sources == []

    def test_dedup_preserves_order(self):
        req = SourceReplaceRequest(sources=["x", "y", "x"])
        assert req.sources == ["x", "y"]

    def test_missing_sources_field_rejected(self):
        with pytest.raises(PydanticValidationError):
            SourceReplaceRequest()


# ═══════════════════════════════════════════════════════════════════════════
# SourceRemoveRequest
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
# CommentUpdateRequest
# ═══════════════════════════════════════════════════════════════════════════


class TestCommentUpdateRequest:
    def test_basic(self):
        req = CommentUpdateRequest(config_id="cfg1", comment="hello")
        assert req.config_id == "cfg1"
        assert req.comment == "hello"

    def test_comment_none_allowed(self):
        req = CommentUpdateRequest(config_id="cfg1", comment=None)
        assert req.comment is None

    def test_config_id_required(self):
        with pytest.raises(PydanticValidationError):
            CommentUpdateRequest(comment="hello")

    def test_config_id_min_length(self):
        with pytest.raises(PydanticValidationError):
            CommentUpdateRequest(config_id="", comment="hello")

    def test_comment_max_length(self):
        req = CommentUpdateRequest(config_id="cfg1", comment="c" * 255)
        assert req.comment == "c" * 255
        with pytest.raises(PydanticValidationError):
            CommentUpdateRequest(config_id="cfg1", comment="c" * 256)

    def test_exclude_none_serialization_drops_comment(self):
        req = CommentUpdateRequest(config_id="cfg1", comment=None)
        dumped = req.model_dump(mode="json", exclude_none=True)
        assert dumped == {"config_id": "cfg1"}
