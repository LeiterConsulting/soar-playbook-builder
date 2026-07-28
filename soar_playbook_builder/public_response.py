"""Helpers that keep internal diagnostics out of REST responses."""

from __future__ import annotations

from typing import Any

_INTERNAL_KEYS = frozenset(
    {
        "trace",
        "traceback",
        "stack",
        "stack_trace",
        "exception",
        "exception_detail",
    }
)


def sanitize_public_payload(value: Any) -> Any:
    """Recursively remove diagnostic-only fields from a response payload."""
    if isinstance(value, dict):
        return {
            key: sanitize_public_payload(item)
            for key, item in value.items()
            if str(key).lower() not in _INTERNAL_KEYS
        }
    if isinstance(value, list):
        return [sanitize_public_payload(item) for item in value]
    return value
