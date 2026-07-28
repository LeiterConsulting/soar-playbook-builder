"""Tests for REST response diagnostic redaction."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from public_response import sanitize_public_payload  # noqa: E402


def test_sanitize_public_payload_removes_nested_diagnostics():
    payload = {
        "status": "error",
        "error": "Request failed",
        "traceback": "secret path",
        "nested": [{"stack_trace": "internal", "safe": "value"}],
    }

    sanitized = sanitize_public_payload(payload)

    assert sanitized == {
        "status": "error",
        "error": "Request failed",
        "nested": [{"safe": "value"}],
    }


def test_sanitize_public_payload_preserves_normal_response_fields():
    payload = {"status": "success", "source": "def on_start(container):\n    pass"}
    assert sanitize_public_payload(payload) == payload
