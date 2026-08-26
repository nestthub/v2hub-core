# V2Hub - VPN Subscription API Client

Professional Python client library for VPN Subscription API with async/sync support, comprehensive error handling, and production-ready features.

### 🌐 Part of the [V2Hub Ecosystem](https://github.com/nestthub/nestthub/blob/main/ecosystems/v2hub/README.md)

This package is one component of V2Hub — see the full project overview, architecture, and all related repositories.

## Features

- 🚀 **Async & Sync**: Both `AsyncVPNClient` and `VPNClient` (sync wrapper)
- 📦 **Pydantic Models**: Full type safety and validation with Pydantic v2
- 🔄 **Smart Retry**: Exponential backoff with jitter and circuit breaker
- 🛡️ **Exception Hierarchy**: Typed exceptions with `is_retryable` and `recovery_hint`
- 🎯 **Type Safe**: Full type hints for IDE support
- 🤝 **Provider Support**: Manage subscriptions on behalf of end-users with a single `as_provider_for_user_id` argument — one client instance can act as both a self-service user and a provider for any number of end-users
- 📊 **Production Ready**: Logging, observability, and middleware support

## Installation

```bash
pip install v2hub
```

## Quick Start

### Async Usage

```python
from v2hub import AsyncVPNClient

async with AsyncVPNClient("https://api.example.com", "your-api-token") as client:
    # Create subscription (optionally with initial sources)
    sub = await client.create_subscription(
        "my-vpn",
        sources=["vless://uuid@server1:443#Server1"],
    )

    # Add more sources later
    await client.add_sources(sub.token, ["vmess://uuid@server2:443#Server2"])

    # Get resolved subscription content (base64-decoded)
    public = await client.get_public_subscription(sub.token)
    print(public.get_configs())
```

### Sync Usage

```python
from v2hub import VPNClient

with VPNClient("https://api.example.com", "your-api-token") as client:
    # Create subscription
    sub = client.create_subscription("my-vpn")

    # Add sources
    client.add_sources(sub.token, ["vless://uuid@server1:443#Server1"])

    # List subscriptions
    subs = client.list_subscriptions()
    for s in subs:
        print(f"{s.name}: {s.token}")
```

### Provider Usage

Providers manage subscriptions on behalf of end-users. A single client instance, authenticated with a **provider** API token, can act for any number of end-users by passing `as_provider_for_user_id` on subscription and source calls. An approved connection to the target `user_id` must exist first.

```python
from v2hub import AsyncVPNClient

async with AsyncVPNClient("https://api.example.com", "provider-api-token") as client:
    # Establish (or re-approve) authorization for an end-user
    await client.create_provider_connection(user_id=12345)

    # Manage that end-user's subscriptions on their behalf
    sub = await client.create_subscription(
        "managed-vpn",
        sources=["vless://uuid@server1:443#Server1"],
        as_provider_for_user_id=12345,
    )
    await client.add_sources(
        sub.token, ["vmess://uuid@server2:443#Server2"], as_provider_for_user_id=12345
    )

    # Revoke access when no longer needed
    await client.revoke_provider_connection(user_id=12345)
```

## Error Handling

```python
from v2hub import (
    AsyncVPNClient,
    VPNAPIError,
    RateLimitError,
    NotFoundError,
)

async with AsyncVPNClient(base_url, token) as client:
    try:
        sub = await client.get_subscription("token123")
    except NotFoundError:
        print("Subscription not found")
    except RateLimitError as e:
        print(f"Rate limited. Retry after: {e.retry_after}")
    except VPNAPIError as e:
        if e.is_retryable:
            print(f"Retryable error: {e.recovery_hint}")
        else:
            print(f"Permanent error: {e}")
```

## Configuration

### Retry Configuration

```python
from v2hub import AsyncVPNClient, RetryConfig

config = RetryConfig(
    max_retries=5,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2,
    jitter=True,
)

client = AsyncVPNClient(
    base_url="https://api.example.com",
    api_token="your-token",
    retry_config=config,
)
```

### Circuit Breaker

```python
from v2hub import AsyncVPNClient, CircuitBreakerConfig, VPNAPIError

breaker = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=VPNAPIError,
)

client = AsyncVPNClient(
    base_url="https://api.example.com",
    api_token="your-token",
    circuit_breaker_config=breaker,
)
```

## API Coverage

Every subscription and source method below accepts an optional, keyword-only `as_provider_for_user_id: int` argument. Omit it for normal self-service calls; pass an end-user's ID to act as a provider on their behalf (requires a provider API token and an approved connection — see [Provider Connections](#provider-connections) below).

### Subscriptions

- `create_subscription(name, description=None, sources=None)` - Create new subscription, optionally with initial sources
- `get_subscription(token)` - Get subscription details
- `list_subscriptions()` - List all subscriptions
- `update_subscription(token, name=None, description=None)` - Update subscription metadata
- `delete_subscription(token)` - Delete subscription
- `refresh_subscription(token)` - Manually refresh external URL sources

### Sources

- `add_sources(token, sources)` - Add sources (accepts plain URI strings, dicts, or `SourceCreate` instances)
- `replace_sources(token, sources)` - Replace all sources
- `remove_sources(token, source_ids)` - Remove specific sources by ID
- `update_source(token, config_id, comment=None, is_hidden=None, max_depth=None)` - Partially update a source's comment, visibility, or nesting depth
- `update_comment(token, config_id, comment)` - **Deprecated**, use `update_source()` instead

### Provider Connections

Require a **provider** API token. Establish and manage the authorization link between a provider and an end-user; a prerequisite for any `as_provider_for_user_id=` call above.

- `create_provider_connection(user_id)` - Create or re-approve authorization for an end-user. Returns a `ProviderConnectionCreateResponse`, which additionally includes a `connection_link`
- `get_provider_connection(user_id)` - Get current authorization status
- `revoke_provider_connection(user_id)` - Revoke authorization (can be re-approved later)
- `delete_provider_connection(user_id)` - Permanently delete the authorization record

### User Self-Service (Me)

Operate on the account tied to your own `api_token` — separate from provider-mode subscription methods and from provider connection management above.

- `get_me()` - Get information about the currently authenticated user
- `list_connections()` - List the current user's provider connections (pending and approved; revoked connections are excluded)
- `get_connection(provider_name)` - Get the current user's connection status for a provider
- `approve_connection(provider_name)` - Approve a pending provider connection request (subject to the server-side `MAX_PROVIDERS_PER_USER` limit)
- `reject_connection(provider_name)` - Reject a pending provider connection request
- `revoke_connection(provider_name)` - Revoke the current user's provider authorization (existing subscriptions from that provider remain available)

```python
from v2hub import AsyncVPNClient

async with AsyncVPNClient("https://api.example.com", "your-api-token") as client:
    me = await client.get_me()
    print(me.user_id, me.is_active)

    connections = await client.list_connections()
    for conn in connections.connections:
        print(conn.provider_name, conn.status)

    # Approve a pending request from a provider
    await client.approve_connection("my-provider")
```

### Public Access

- `get_public_subscription(token)` - Get the resolved subscription (base64-encoded configs + title), no auth required. Returns a `PublicSubscriptionResponse` with `.decode()`, `.get_configs()`, and `.config_count` helpers.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## Extensions

- **[v2hub-admin](https://github.com/nestthub/v2hub-admin)**: Admin API extension with HMAC authentication
- **[v2hub-cli](https://github.com/nestthub/v2hub-cli)**: Beautiful command-line interface

## License

MIT License - see LICENSE file for details.

## Author

nestt
