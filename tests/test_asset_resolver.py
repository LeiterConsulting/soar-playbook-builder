"""Tests for asset preflight / resolver."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from asset_resolver import (  # noqa: E402
    apply_asset_map_to_source,
    extract_required_asset_keys,
    resolve_asset_requirements,
)
from builder_helpers import SCAFFOLDS  # noqa: E402


def test_extract_servicenow_assets():
    source = SCAFFOLDS["servicenow-incident"]
    keys = extract_required_asset_keys(source)
    assert "servicenow" in keys
    assert "soar" not in keys


def test_auto_map_single_candidate():
    source = SCAFFOLDS["servicenow-incident"]
    configured = [
        {"id": 1, "name": "snow_lab", "product_name": "ServiceNow", "product_code": "servicenow"},
    ]
    result = resolve_asset_requirements(source, configured)
    assert result["ready"] is True
    assert result["asset_map"]["servicenow"] == "snow_lab"
    assert "soar" not in result["asset_map"]


def test_missing_asset_blocks_ready():
    source = SCAFFOLDS["servicenow-incident"]
    result = resolve_asset_requirements(source, [])
    assert result["ready"] is False
    assert "servicenow" in result["missing"]


def test_soar_ignores_mcp_bridge_assets():
    source = 'phantom.act("add note", assets=["soar"], name="n", container=container)'
    configured = [
        {"id": 2, "name": "soar mcp bridge", "product_name": "SOAR Playbook Builder"},
    ]
    result = resolve_asset_requirements(source, configured)
    soar_req = next(r for r in result["requirements"] if r["key"] == "soar")
    assert soar_req["status"] == "missing"
    assert result["ready"] is False


def test_okta_scaffold_needs_okta_only():
    source = SCAFFOLDS["okta-idp-response"]
    keys = extract_required_asset_keys(source)
    assert "okta" in keys
    assert "soar" not in keys
    configured = [
        {"id": 1, "name": "okta", "product_name": "Okta", "product_code": "okta"},
    ]
    result = resolve_asset_requirements(source, configured)
    assert result["ready"] is True


def test_apply_asset_map_rewrites_source():
    source = 'phantom.act("x", assets=["servicenow"], name="a")'
    mapped = apply_asset_map_to_source(source, {"servicenow": "snow_lab"})
    assert 'assets=["snow_lab"]' in mapped


if __name__ == "__main__":
    test_extract_servicenow_assets()
    test_auto_map_single_candidate()
    test_missing_asset_blocks_ready()
    test_soar_ignores_mcp_bridge_assets()
    test_okta_scaffold_needs_okta_only()
    test_apply_asset_map_rewrites_source()
    print("ok")
