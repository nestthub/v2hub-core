from __future__ import annotations

from v2hub.models.base import BaseModelConfig
from v2hub.models.providers import ProviderAuthorizationStatus


class MeResponse(BaseModelConfig):
    user_id: int
    is_active: bool


class ConnectionResponse(BaseModelConfig):
    provider_name: str
    provider_url: str | None
    is_authorized: bool
    status: ProviderAuthorizationStatus | None = None


class ConnectionsResponse(BaseModelConfig):
    connections: list[ConnectionResponse]
