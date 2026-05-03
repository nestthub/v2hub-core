from __future__ import annotations

import base64
from typing import Annotated, Optional

from pydantic import Field

from .base import BaseModelConfig


# ═══════════════════════════════════════════════════════════════════════════
# Public Endpoint Models
# ═══════════════════════════════════════════════════════════════════════════


class PublicSubscriptionResponse(BaseModelConfig):
    """Response from public subscription endpoint (base64 encoded configs)."""

    title: Annotated[Optional[str], Field(default="v2hub", description="Base64-encoded subscription title")] = "v2hub"
    content: Annotated[str, Field(description="Base64-encoded subscription content")]

    def decode(self) -> str:
        """
        Decode base64 content to plain text.

        Returns:
            Decoded content string

        Raises:
            ValueError: If content is not valid base64
        """
        try:
            decoded_bytes = base64.b64decode(self.content)
            return decoded_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decode base64 content: {e}") from e

    def get_configs(self) -> list[str]:
        """
        Get list of individual configs.

        Returns:
            List of configuration strings
        """
        decoded = self.decode()
        return [line.strip() for line in decoded.split("\n") if line.strip()]

    @property
    def config_count(self) -> int:
        """Get number of configs."""
        return len(self.get_configs())
