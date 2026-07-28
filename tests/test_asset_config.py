"""Tests for asset configuration export/import."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from asset_config import (  # noqa: E402
    export_asset_config_payload,
    import_asset_config_payload,
)


def test_export_redacts_secrets_by_default():
    cfg = {
        "mcp_bridge_url": "http://127.0.0.1:8003/agent",
        "asset_defaults": '{"okta":"okta"}',
        "soar_rest_token": "secret-token",
    }
    out = export_asset_config_payload(cfg)
    assert out["status"] == "success"
    assert out["configuration"]["mcp_bridge_url"] == cfg["mcp_bridge_url"]
    assert out["configuration"]["soar_rest_token"] == "***REDACTED***"
    assert out["secrets_redacted"] is True
    blob = json.loads(out["copy_json"])
    assert blob["configuration"]["soar_rest_token"] == "***REDACTED***"


def test_export_include_secrets():
    cfg = {"soar_rest_token": "secret-token", "ai_instructions": "lab"}
    out = export_asset_config_payload(cfg, include_secrets=True)
    assert out["configuration"]["soar_rest_token"] == "secret-token"


def test_import_preview_requires_confirm():
    cfg = {"asset_defaults": "{}"}
    bundle = {"configuration": {"ai_instructions": "new lab", "asset_defaults": '{"slack":"slack"}'}}
    out = import_asset_config_payload(None, cfg, config_json=json.dumps(bundle), confirm=False)
    assert out["needs_confirm"] is True
    assert "ai_instructions" in out["import_keys"]


def test_import_rejects_redacted_secret():
    cfg = {}
    bundle = {"configuration": {"soar_rest_token": "***REDACTED***", "ai_instructions": "x"}}
    out = import_asset_config_payload(None, cfg, config_json=json.dumps(bundle), confirm=False)
    assert "soar_rest_token" not in (out.get("proposed_configuration") or {})
    assert "ai_instructions" in (out.get("proposed_configuration") or {})


if __name__ == "__main__":
    for fn in (
        test_export_redacts_secrets_by_default,
        test_export_include_secrets,
        test_import_preview_requires_confirm,
        test_import_rejects_redacted_secret,
    ):
        fn()
        print(f"OK {fn.__name__}")
    print("All asset_config tests passed")
