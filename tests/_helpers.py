"""
Helpers for writing tests that check *semantics* rather than *exact shape*.

The sources fields on request models started as list[str] and, in a
backward-compatible change, became list[SourceCreate] (each with data/
is_hidden/max_depth, defaulting to False/3 for plain-string input). Old
caller code (`sources=["vless://a"]`) still works after that change --
only the *internal representation* changed, not what a str input produces.

Tests that hard-code `assert req.sources == ["a", "b"]` break on any such
wrapping, even though nothing is actually broken for the caller. These
helpers pull out just the "data" value for comparison, so tests keep
validating real behavior (does the source data round-trip correctly?)
without being coupled to whether it's stored as a bare str or an object.

If the update genuinely breaks backward compatibility (a plain string
input is rejected, or the data value is silently dropped/altered), these
helpers will still fail the test -- that's a real regression, not shape
noise.
"""

from __future__ import annotations

from typing import Any


def source_data(item: Any) -> str:
    """
    Extract the underlying source data string from a sources-list item,
    regardless of whether the model represents it as a bare str or as an
    object (SourceCreate / dict) with a `.data` / `["data"]` field.
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item["data"]
    # pydantic model instance (e.g. SourceCreate)
    if hasattr(item, "data"):
        return item.data
    raise TypeError(f"Cannot extract source data from {item!r}")


def source_data_list(items: list[Any]) -> list[str]:
    """Apply source_data() across a whole sources list, preserving order."""
    return [source_data(item) for item in items]


def get_attr_or_key(item: Any, name: str, default: Any = None) -> Any:
    """
    Read an optional field (e.g. is_hidden, max_depth) off a sources-list
    item that might be a bare str (no such field -> default), a dict, or
    a pydantic model instance.
    """
    if isinstance(item, str):
        return default
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def wire_source_data_list(payload_sources: list[Any]) -> list[str]:
    """
    Like source_data_list(), but for an already-JSON-serialized payload
    (e.g. the body captured off a mocked HTTP request), where items are
    plain str or plain dict -- never pydantic model instances.
    """
    result = []
    for item in payload_sources:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            result.append(item["data"])
        else:
            raise TypeError(f"Unexpected source payload item: {item!r}")
    return result
