from __future__ import annotations

import warnings
from typing import Annotated, Any

import typing_extensions
from pydantic import Field, field_validator, model_validator

from .base import BaseModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════


class SourceCreate(BaseModelConfig):
    data: Annotated[str, Field(description="Source data (config, URL, or token)", min_length=1)]
    is_hidden: Annotated[
        bool | None, Field(description="Whether the source is hidden from end users", default=None)
    ] = None
    max_depth: Annotated[
        int | None,
        Field(
            description="Max nesting depth for source visibility propagation (0-3)",
            ge=0,
            le=3,
            default=None,
        ),
    ] = None


def _normalize_sources(v: list[str | dict[str, Any] | SourceCreate]) -> list[dict[str, Any]]:
    """
    Normalize a list of sources into deduplicated SourceCreate-shaped dicts.

    Shared by SourceAddRequest and SourceReplaceRequest so both endpoints
    accept the same input shapes and apply identical dedup/cleaning rules.

    Accepts plain strings (shorthand for {"data": <string>}), dicts, or
    SourceCreate instances. Deduplicates by the (stripped) `data` value,
    preserving first-occurrence order.
    """
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in v:
        if isinstance(item, str):
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            cleaned.append({"data": key})
        elif isinstance(item, SourceCreate):
            key = item.data.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            item_dict = item.model_dump()
            item_dict["data"] = key
            cleaned.append(item_dict)
        elif isinstance(item, dict):
            key = (item.get("data") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            item = dict(item)
            item["data"] = key
            cleaned.append(item)
        else:
            raise TypeError("Each source must be a string, dict, or SourceCreate")

    return cleaned


class SubscriptionCreateRequest(BaseModelConfig):
    """Request to create a new subscription."""

    name: Annotated[str, Field(description="Subscription name", min_length=1, max_length=64)]
    description: Annotated[
        str | None, Field(None, description="Optional description", max_length=255)
    ] = None
    sources: Annotated[
        list[SourceCreate], Field(default_factory=list, description="Initial sources")
    ]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate subscription name."""
        v = v.strip()
        if not v:
            raise ValueError("Subscription name cannot be empty")
        return v

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(
        cls, v: list[str | dict[str, Any] | SourceCreate] | None
    ) -> list[dict[str, Any]]:
        """Validate and deduplicate sources."""
        if v is None:
            return []
        return _normalize_sources(v)


class SubscriptionUpdateRequest(BaseModelConfig):
    name: Annotated[
        str | None, Field(None, description="New name", min_length=1, max_length=64)
    ] = None
    description: Annotated[
        str | None, Field(None, description="New description", max_length=64)
    ] = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> SubscriptionUpdateRequest:
        """Ensure at least one field is provided."""
        if self.name is None and self.description is None:
            raise ValueError("At least one field must be provided for update")
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate subscription name."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Subscription name cannot be empty")
        return v


class SourceAddRequest(BaseModelConfig):
    """Request to add sources to subscription."""

    sources: Annotated[list[SourceCreate], Field(description="Sources to add", min_length=1)]

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, v: list[str | dict[str, Any] | SourceCreate]) -> list[dict[str, Any]]:
        """Validate and deduplicate sources."""
        cleaned = _normalize_sources(v)
        if not cleaned:
            raise ValueError("At least one valid source must be provided")
        return cleaned


class SourceReplaceRequest(BaseModelConfig):
    """Request to replace all sources in subscription."""

    sources: Annotated[list[SourceCreate], Field(description="New sources (replaces all)")]

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, v: list[str | dict[str, Any] | SourceCreate]) -> list[dict[str, Any]]:
        """Validate and deduplicate sources."""
        return _normalize_sources(v)


class SourceRemoveRequest(BaseModelConfig):
    """Request to remove specific sources."""

    source_ids: Annotated[list[str], Field(description="Source IDs to remove", min_length=1)]

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, v: list[str]) -> list[str]:
        """Validate and deduplicate source IDs."""
        v = [s.strip() for s in v if s.strip()]
        if not v:
            raise ValueError("At least one valid source ID must be provided")
        return list(dict.fromkeys(v))


class SourceUpdateRequest(BaseModelConfig):
    """
    Request to partially update a source within a subscription.

    Replaces CommentUpdateRequest (deprecated below): supports the same
    comment update, plus is_hidden and max_depth. Only fields explicitly
    provided are changed; omitted fields are left untouched.
    """

    config_id: Annotated[str, Field(description="Config id", min_length=1)]
    comment: Annotated[str | None, Field(None, description="Comment text", max_length=255)] = None
    is_hidden: Annotated[
        bool | None, Field(None, description="Whether the source is hidden from end users")
    ] = None
    max_depth: Annotated[
        int | None,
        Field(
            None,
            description="Max nesting depth for source visibility propagation (0-3)",
            ge=0,
            le=3,
        ),
    ] = None

    @field_validator("config_id")
    @classmethod
    def validate_config_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("config_id cannot be empty")
        return v


@typing_extensions.deprecated(
    "The `CommentUpdateRequest` class is deprecated; use `SourceUpdateRequest` instead.",
    category=None,
)
class CommentUpdateRequest(BaseModelConfig):
    """
    Request to update config comment.

    .. deprecated::
        Use :class:`SourceUpdateRequest` instead, which supports the same
        comment update plus ``is_hidden`` and ``max_depth``. This model
        still works and is fully supported, but will not receive further
        updates and may be removed in a future major version.
    """

    config_id: Annotated[str, Field(description="Config id", min_length=1)]
    comment: Annotated[str | None, Field(None, description="Comment text", max_length=255)]

    def __init__(self, **data: Any) -> None:
        warnings.warn(
            "CommentUpdateRequest is deprecated and will not receive further "
            "updates; use SourceUpdateRequest instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**data)
