"""
Pydantic models for v2hub API.

Fully typed models with validation, serialization, and documentation.
"""

from __future__ import annotations

__all__ = [
    "CommentUpdateRequest",
    "ErrorResponse",
    "PublicSubscriptionResponse",
    "RefreshSubscriptionResponse",
    "Source",
    "SourceAddRequest",
    "SourceRemoveRequest",
    "SourceReplaceRequest",
    "SourceType",
    "Subscription",
    "SubscriptionCreateRequest",
    "SubscriptionListItem",
    "SubscriptionUpdateRequest",
]


from .enums import SourceType
from .public import PublicSubscriptionResponse
from .requests import (
    CommentUpdateRequest,
    SourceAddRequest,
    SourceRemoveRequest,
    SourceReplaceRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
)
from .responses import (
    ErrorResponse,
    RefreshSubscriptionResponse,
)
from .sources import Source
from .subscriptions import Subscription, SubscriptionListItem
