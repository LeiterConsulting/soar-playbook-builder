"""Environment check payload for NL / MCP readiness."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from environment_check import environment_check_payload  # noqa: E402


@patch("environment_check._probe_bridge")
def test_environment_check_bridge_online(mock_probe):
    mock_probe.return_value = {"reachable": True, "llm_configured": True, "llm_model": "gpt-4o-mini"}
    cfg = {"mcp_bridge_url": "http://127.0.0.1:8080", "asset_defaults": '{"okta":"okta"}'}
    out = environment_check_payload(object(), cfg)
    assert out["status"] == "success"
    assert out["nl_mode"] == "llm"
    assert out["nl_ready"] is True
    assert out["bridge_reachable"] is True
    assert out["llm_configured"] is True
    assert any(c["id"] == "mcp_bridge" and c["severity"] == "ok" for c in out["checks"])
    assert any(c["id"] == "llm" and c["severity"] == "ok" for c in out["checks"])


@patch("environment_check._probe_bridge")
def test_environment_check_bridge_online_no_llm(mock_probe):
    mock_probe.return_value = {
        "reachable": True,
        "llm_configured": False,
        "llm_hint": "Set OPENAI_API_KEY on MCP bridge host",
    }
    cfg = {"mcp_bridge_url": "http://127.0.0.1:8080"}
    out = environment_check_payload(object(), cfg)
    assert out["nl_mode"] == "bridge_stub"
    assert out["nl_ready"] is False
    assert out["llm_configured"] is False
    assert any(c["id"] == "llm" and c["severity"] == "warn" for c in out["checks"])
    assert any(f["id"] == "configure_llm" for f in out["fixes"])


@patch("environment_check._probe_bridge")
def test_environment_check_bridge_offline_still_usable(mock_probe):
    mock_probe.return_value = {"reachable": False, "hint": "Connection refused"}
    cfg = {"mcp_bridge_url": "http://127.0.0.1:8080"}
    out = environment_check_payload(object(), cfg)
    assert out["nl_mode"] == "offline_templates"
    assert out["nl_ready"] is True
    assert out["bridge_reachable"] is False
    fix_ids = {f["id"] for f in out["fixes"]}
    assert "use_template" in fix_ids
    assert "provision_demo" in fix_ids
