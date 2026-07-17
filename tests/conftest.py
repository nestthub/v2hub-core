from __future__ import annotations

from datetime import datetime, timezone

import pytest

BASE_URL = "https://api.example.com"
API_TOKEN = "test-token-123"


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def api_token() -> str:
    return API_TOKEN


def make_source_dict(
    id: str = "src1",
    source_type: str = "config",
    data: str = "vless://uuid@server:443#Server1",
    order_index: int = 0,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": id,
        "source_type": source_type,
        "data": data,
        "order_index": order_index,
        "created_at": now,
        "updated_at": now,
    }


def make_subscription_dict(
    token: str = "sub-token-abc",
    name: str = "My VPN",
    description: str | None = None,
    sources: list | None = None,
    sources_count: int | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    sources = sources if sources is not None else [make_source_dict()]
    return {
        "token": token,
        "name": name,
        "description": description,
        "sources": sources,
        "sources_count": sources_count if sources_count is not None else len(sources),
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
def source_dict_factory():
    return make_source_dict


@pytest.fixture
def subscription_dict_factory():
    return make_subscription_dict
