# V2Hub - VPN Subscription API Client

Professional Python client library for VPN Subscription API with async/sync support, comprehensive error handling, and production-ready features.

## Features

- 🚀 **Async & Sync**: Both `AsyncVPNClient` and `VPNClient` (sync wrapper)
- 📦 **Pydantic Models**: Full type safety and validation with Pydantic v2
- 🔄 **Smart Retry**: Exponential backoff with jitter and circuit breaker
- 🛡️ **Exception Hierarchy**: 11 typed exceptions with `is_retryable` and `recovery_hint`
- 🎯 **Type Safe**: Full type hints for IDE support
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
    # Create subscription
    sub = await client.create_subscription("my-vpn")

    # Add sources
    await client.add_sources(sub.token, ["vless://server1", "vmess://server2"])

    # Get subscription config
    config = await client.get_subscription_config(sub.token)
    print(config)
```

### Sync Usage

```python
from v2hub import VPNClient

with VPNClient("https://api.example.com", "your-api-token") as client:
    # Create subscription
    sub = client.create_subscription("my-vpn")

    # Add sources
    client.add_sources(sub.token, ["vless://server1"])

    # List subscriptions
    subs = client.list_subscriptions()
    for s in subs:
        print(f"{s.name}: {s.token}")
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
from v2hub import AsyncVPNClient, CircuitBreakerConfig

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

### Subscriptions

- `create_subscription(name, comment?)` - Create new subscription
- `get_subscription(token)` - Get subscription details
- `list_subscriptions()` - List all subscriptions
- `update_subscription(token, name?, comment?)` - Update subscription
- `delete_subscription(token)` - Delete subscription
- `refresh_subscription(token)` - Refresh subscription config

### Sources

- `add_sources(token, uris)` - Add source URIs
- `replace_sources(token, uris)` - Replace all sources
- `remove_sources(token, uris)` - Remove specific sources
- `get_sources(token)` - Get all sources for subscription

### Public Access

- `get_subscription_config(token)` - Get public subscription config (no auth)
- `get_public_info(token)` - Get public subscription metadata (no auth)

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
