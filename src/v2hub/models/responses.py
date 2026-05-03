from __future__ import annotations

from typing import Annotated, Any, List, Optional

from pydantic import Field

from .base import BaseModelConfig


# ═══════════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════════


class RefreshSubscriptionResponse(BaseModelConfig):
    """Response from manual refresh operation."""
    refreshed: Annotated[int, Field(0, description="Number of successfully refreshed sources")]
    failed: Annotated[int, Field(0, description="Number of sources that failed to refresh")]
    skipped: Annotated[int, Field(0, description="Number of sources skipped during refresh")]
    total: Annotated[int, Field(0, description="Total URLs processed")]
    
    message: Optional[str] = Field(None, description="Optional status message")
    errors: Optional[List[str]] = Field(
        None,
        description="List of errors per URL",
        json_schema_extra={
            "example": [
                "https://example.com: timeout",
                "https://bad.url: invalid format"
            ]
        },
    )


class ErrorResponse(BaseModelConfig):
    """API error response."""

    error: Annotated[str, Field(description="Error code/type", min_length=1)]
    message: Annotated[str, Field(description="Human-readable error message", min_length=1)]
    details: Annotated[dict[str, Any] | None, Field(None, description="Additional error details")]



