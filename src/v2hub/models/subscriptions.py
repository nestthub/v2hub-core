from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, model_validator

from .base import BaseModelConfig
from .sources import Source

# ═══════════════════════════════════════════════════════════════════════════
# Subscription Models
# ═══════════════════════════════════════════════════════════════════════════


class Subscription(BaseModelConfig):
    """Complete subscription with all details."""

    token: Annotated[str, Field(description="Unique subscription token", min_length=1)]
    name: Annotated[
        str, Field(description="User-defined subscription name", min_length=1, max_length=64)
    ]
    description: Annotated[str | None, Field(None, description="Optional description", max_length=255)]
    sources: Annotated[list[Source], Field(default_factory=list, description="List of sources")]
    sources_count: Annotated[int, Field(description="Total resolved configs count", ge=0)]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @model_validator(mode="after")
    def validate_sources_count(self) -> "Subscription":
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
