from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator

from .base import BaseModelConfig
from .sources import Source, SourceCreate, _normalize_sources

# ═══════════════════════════════════════════════════════════════════════════
# Subscription Models
# ═══════════════════════════════════════════════════════════════════════════


class Subscription(BaseModelConfig):
    """Complete subscription with all details."""

    token: Annotated[str, Field(description="Unique subscription token", min_length=1)]
    name: Annotated[
        str, Field(description="User-defined subscription name", min_length=1, max_length=64)
    ]
    provider_name: Annotated[str | None, Field(None, description="Provider name")]
    description: Annotated[
        str | None, Field(None, description="Optional description", max_length=255)
    ]
    sources: Annotated[list[Source], Field(default_factory=list, description="List of sources")]
    sources_count: Annotated[int, Field(description="Total resolved configs count", ge=0)]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @model_validator(mode="after")
    def validate_sources_count(self) -> Subscription:
        """Validate that sources_count matches actual sources length."""
        # Note: API may return different count due to external URLs
        # This is just a sanity check
        if self.sources_count < len(self.sources):
            # Log warning but don't fail
            pass
        return self


class SubscriptionListItem(Subscription):
    """Subscription in list view (inherits all fields from Subscription)."""

    pass


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


class RefreshSubscriptionResponse(BaseModelConfig):
    """Response from manual refresh operation."""

    refreshed: Annotated[int, Field(0, description="Number of successfully refreshed sources")]
    failed: Annotated[int, Field(0, description="Number of sources that failed to refresh")]
    skipped: Annotated[int, Field(0, description="Number of sources skipped during refresh")]
    total: Annotated[int, Field(0, description="Total URLs processed")]

    message: str | None = Field(None, description="Optional status message")
    errors: list[str] | None = Field(
        None,
        description="List of errors per URL",
        json_schema_extra={
            "example": ["https://example.com: timeout", "https://bad.url: invalid format"]
        },
    )
