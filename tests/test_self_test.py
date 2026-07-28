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
    assert "deterministic_compiler" in ids
    assert "deterministic_preflight" in ids
    assert "canonical_ir_templates" in ids
    assert "trusted_review_lock" in ids
    assert "organization_templates" in ids
    compiler = next(c for c in out["checks"] if c["id"] == "deterministic_compiler")
    assert compiler["status"] == "ok"
    validator = next(c for c in out["checks"] if c["id"] == "deterministic_preflight")
    assert validator["status"] == "ok"
    review_lock = next(
        c for c in out["checks"] if c["id"] == "trusted_review_lock"
    )
    assert review_lock["status"] == "ok"


def test_self_test_warns_when_legacy_org_python_is_ignored():
    out = run_self_test(
        {
            "custom_templates_json": (
                '{"templates":[{"id":"org-legacy-demo",'
                '"source":"def on_start(container):\\n    pass"}]}'
            )
        }
    )
    boundary = next(
        c for c in out["checks"] if c["id"] == "organization_templates"
    )
    assert boundary["status"] == "warn"
    assert "ignored" in boundary["detail"]


def test_self_test_bridge_probe():
    out = run_self_test(
        {"mcp_bridge_url": "http://127.0.0.1:8003/agent"},
        bridge_probe=lambda: {"reachable": True, "llm_configured": False, "llm_hint": "no key"},
    )
    bridge = next(c for c in out["checks"] if c["id"] == "mcp_bridge")
    assert bridge["status"] == "ok"


def test_self_test_flags_insecure_transport_overrides():
    out = run_self_test({"soar_loopback_allow_insecure_tls": True})
    transport = next(c for c in out["checks"] if c["id"] == "transport_security")
    assert transport["status"] == "warn"
    assert out["status"] == "needs_attention"


if __name__ == "__main__":
    test_self_test_runs_offline()
    print("OK test_self_test_runs_offline")
    test_self_test_bridge_probe()
    print("OK test_self_test_bridge_probe")
    test_self_test_flags_insecure_transport_overrides()
    print("OK test_self_test_flags_insecure_transport_overrides")
    print("All self_test tests passed")
