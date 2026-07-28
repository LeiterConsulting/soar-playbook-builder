"""Tests for ES → sidecar link resolution (no phantom)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from es_link import (  # noqa: E402
    _artifact_matches_event,
    build_sidecar_chat_url,
    es_link_status_message,
    resolve_es_link_params,
)


def test_artifact_matches_event():
    art = {"cef": {"event_id": "abc-123"}, "cef_value": ""}
    assert _artifact_matches_event(art, "abc-123")
    assert not _artifact_matches_event(art, "other")


def test_build_sidecar_chat_url():
    url = build_sidecar_chat_url(
        "https://soar/rest/handler/dir/asset",
        {"container_id": 42, "event_id": "e1", "rule_name": "Failed Logins"},
    )
    assert "container_id=42" in url
    assert "event_id=e1" in url
    assert "rule_name=Failed" in url
    assert url.endswith("/chat") or "/chat?" in url


def test_resolve_without_lookup():
    param = resolve_es_link_params(
        event_id="ev-1",
        rule_name="Test Rule",
        container_id=99,
        request=None,
    )
    assert param["container_id"] == 99
    assert param["event_id"] == "ev-1"
    msg = es_link_status_message(param)
    assert "case 99" in msg


if __name__ == "__main__":
    test_artifact_matches_event()
    test_build_sidecar_chat_url()
    test_resolve_without_lookup()
    print("ok")
