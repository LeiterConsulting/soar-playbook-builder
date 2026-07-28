"""Tests for offline troubleshooting catalog."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from troubleshooting_catalog import (  # noqa: E402
    attach_troubleshooting,
    match_troubleshooting,
    search_troubleshooting,
)


def test_match_mcp_unreachable():
    entry = match_troubleshooting("MCP bridge unreachable from SOAR at http://127.0.0.1:8003")
    assert entry is not None
    assert entry["id"] in ("mcp_bridge_unreachable", "templates_only")


def test_match_needs_assets_status():
    entry = match_troubleshooting("", status="needs_assets")
    assert entry is not None
    assert entry["id"] == "needs_assets"


def test_match_invalid_datapath():
    entry = match_troubleshooting("Visual editor shows invalid datapath on action block")
    assert entry is not None
    assert entry["id"] == "vpe_invalid_datapath"


def test_attach_on_import_error():
    payload = attach_troubleshooting(
        {"status": "error", "error": "Auto-import failed: SCM sync timeout"}
    )
    assert "troubleshooting" in payload
    assert payload["troubleshooting"]["fix_steps"]


def test_search_okta():
    hits = search_troubleshooting("okta asset")
    assert any(h["id"] == "okta_asset_missing" for h in hits)


def test_search_empty_returns_all():
    assert len(search_troubleshooting()) >= 10


if __name__ == "__main__":
    test_match_mcp_unreachable()
    test_match_needs_assets_status()
    test_match_invalid_datapath()
    test_attach_on_import_error()
    test_search_okta()
    test_search_empty_returns_all()
    print("ok")
