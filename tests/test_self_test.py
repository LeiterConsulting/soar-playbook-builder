"""Tests for post-install self-test."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from self_test import run_self_test  # noqa: E402


def test_self_test_runs_offline():
    out = run_self_test({"asset_defaults": '{"okta":"okta"}'})
    assert out["status"] in ("success", "needs_attention")
    assert out["check_count"] >= 4
    ids = {c["id"] for c in out["checks"]}
    assert "hello_template" in ids
    assert "demo_samples" in ids


def test_self_test_bridge_probe():
    out = run_self_test(
        {"mcp_bridge_url": "http://127.0.0.1:8003/agent"},
        bridge_probe=lambda: {"reachable": True, "llm_configured": False, "llm_hint": "no key"},
    )
    bridge = next(c for c in out["checks"] if c["id"] == "mcp_bridge")
    assert bridge["status"] == "ok"


if __name__ == "__main__":
    test_self_test_runs_offline()
    print("OK test_self_test_runs_offline")
    test_self_test_bridge_probe()
    print("OK test_self_test_bridge_probe")
    print("All self_test tests passed")
