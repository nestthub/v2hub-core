"""
Pydantic models for v2hub API.

Fully typed models with validation, serialization, and documentation.
"""

from __future__ import annotations

__all__ = [
    "SourceType",
    "Source",
    "Subscription",
    "SubscriptionListItem",
    "SubscriptionCreateRequest",
    "SubscriptionUpdateRequest",
    "SourceAddRequest",
    "SourceReplaceRequest",
    "SourceRemoveRequest",
    "CommentUpdateRequest",
    "RefreshSubscriptionResponse",
    "ErrorResponse",
    "PublicSubscriptionResponse",
]


from .enums import SourceType

from .sources import Source
from .subscriptions import Subscription, SubscriptionListItem

from .requests import (
    SubscriptionCreateRequest, SubscriptionUpdateRequest,
    SourceAddRequest, SourceReplaceRequest, SourceRemoveRequest,
    CommentUpdateRequest,
)

from .responses import (
    RefreshSubscriptionResponse, ErrorResponse,
)

from .public import PublicSubscriptionResponse
