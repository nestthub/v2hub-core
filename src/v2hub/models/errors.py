from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from .base import BaseModelConfig


class ErrorResponse(BaseModelConfig):
    """API error response."""

    error: Annotated[str, Field(description="Error code/type", min_length=1)]
    message: Annotated[str, Field(description="Human-readable error message", min_length=1)]
    details: Annotated[dict[str, Any] | None, Field(None, description="Additional error details")]
