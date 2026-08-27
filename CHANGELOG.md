# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Expanded the test suite across HTTP middleware/client, retry logic, request
  models, sync/async clients, and public API.
- Added coverage for previously untested middleware, retry, request normalization,
  error-handling, metadata fallback, and "Me / Connections" API paths.
- The test suite now contains **367 tests**, all passing.

## [1.1.2] - Released

### Added

- User self-service ("me") API for both `VPNClient` and `AsyncVPNClient`, scoped to the
  account associated with the current `api_token`:

  - `get_me()` — get information about the currently authenticated user.
  - `list_connections()` — list the current user's provider connections (pending and
    approved; revoked connections are excluded).
  - `get_connection(provider_name)` — get the current user's connection status for a
    provider.
  - `approve_connection(provider_name)` — approve a pending provider connection request
    (subject to the server-side `MAX_PROVIDERS_PER_USER` limit).
  - `reject_connection(provider_name)` — reject a pending provider connection request.
  - `revoke_connection(provider_name)` — revoke the current user's provider authorization
    (the authorization record is preserved as `REVOKED` so existing subscriptions remain
    available).

- New models: `MeResponse`, `ConnectionResponse`, `ConnectionsResponse`
  (`v2hub.models.me`), importable via `v2hub.models`.
- `ProviderAuthorizationStatus.PENDING` value, plus an `UNKNOWN` fallback member returned
  for any status value the client doesn't recognize (via `_missing_`), so older client
  versions degrade gracefully against newer servers instead of raising a validation error.
- `ProviderConnectionCreateResponse` model (extends `ProviderConnectionResponse` with a
  `connection_link` field).

### Changed

- `create_provider_connection(user_id)` on both clients now returns
  `ProviderConnectionCreateResponse` instead of `ProviderConnectionResponse`. The new type
  is backward compatible (it's a subclass that adds `connection_link`), but code with
  strict `isinstance`/type checks against `ProviderConnectionResponse` alone should be
  reviewed.
- Documented the "Me" endpoints and the `create_provider_connection` return-type change in
  `README.md`.
- Bumped package version to `1.1.2` in `pyproject.toml`.

### Fixed

- Cleaned up an inconsistent import in `client.py`: `ConnectionResponse`,
  `ConnectionsResponse`, and `MeResponse` were imported from the internal
  `v2hub.models.me` submodule in a separate statement instead of from the public
  `v2hub.models` package like every other model. Consolidated into a single, alphabetized
  import from `v2hub.models`.

## [1.1.1] and earlier

Not tracked in this file. See the [GitHub commit history](https://github.com/nestthub/v2hub-core/commits/main)
for changes prior to 1.1.2.
