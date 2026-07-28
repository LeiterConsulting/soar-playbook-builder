"""Tests for sidecar URL query building."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from sidecar_url import append_query, build_sidecar_query_params  # noqa: E402


def test_build_sidecar_query_params_mode():
    pairs = build_sidecar_query_params(
        {"container_id": 1, "mode": "coach", "tab": "respond"}
    )
    assert ("mode", "coach") in pairs
    assert ("tab", "respond") in pairs


def test_build_sidecar_query_params():
    pairs = build_sidecar_query_params(
        {"playbook_id": 216, "container_id": 12345, "rule_name": "Failed Logins"}
    )
    assert ("playbook_id", "216") in pairs
    assert ("container_id", "12345") in pairs
    assert ("rule_name", "Failed Logins") in pairs


def test_append_query():
    url = append_query("https://soar/rest/handler/x/y/chat", [("container_id", "99")])
    assert "container_id=99" in url


if __name__ == "__main__":
    test_build_sidecar_query_params()
    test_append_query()
    print("ok")
