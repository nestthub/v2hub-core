from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field, field_validator

from .base import BaseModelConfig
from .enums import SourceType

# ═══════════════════════════════════════════════════════════════════════════
# Source Models
# ═══════════════════════════════════════════════════════════════════════════


class Source(BaseModelConfig):
    """Individual source within a subscription."""

    id: Annotated[str, Field(description="Unique source identifier (hash)", min_length=1)]
    source_type: Annotated[SourceType, Field(description="Type of source")]
    data: Annotated[str, Field(description="Source data (config, URL, or token)", min_length=1)]
    order_index: Annotated[int, Field(description="Display order", ge=0)]
    is_hidden: Annotated[bool, Field(description="Whether the source is hidden from end users", default=False)]
    max_depth: Annotated[int, Field(description="Max nesting depth for source visibility propagation (0-3)", ge=0, le=3, default=3)]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: str, info: Any) -> str:
        """Validate source data based on type."""
        # Add custom validation logic here
        if not v or not v.strip():
            raise ValueError("Source data cannot be empty")
        return v.strip()

