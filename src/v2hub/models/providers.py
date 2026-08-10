from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field

from .base import BaseModelConfig


class ProviderAuthorizationStatus(str, Enum):
    APPROVED = "approved"
    REVOKED = "revoked"


class ProviderConnectionRequest(BaseModelConfig):
    """Request to create a provider connection for a user."""

    user_id: Annotated[
        int,
        Field(
            description="Target user ID",
            gt=0,
        ),
    ]


class ProviderConnectionResponse(BaseModelConfig):
    """Response containing provider connection status."""

    user_id: Annotated[
        int,
        Field(description="User ID"),
    ]
    status: Annotated[
        ProviderAuthorizationStatus,
        Field(description="Authorization status"),
    ]


class ProviderConnectionDeleteResponse(BaseModelConfig):
    """Response returned after deleting a provider connection."""

    detail: Annotated[
        str,
        Field(description="Operation result"),
    ]
