"""Environment fix — discover and merge asset_defaults."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from environment_fix import (  # noqa: E402
    apply_environment_fixes_payload,
    discover_suggested_defaults,
    persist_asset_defaults,
)


def test_discover_suggested_defaults_single_match():
    configured = [
        {"id": 1, "name": "okta", "product_name": "Okta", "product_code": "okta"},
        {"id": 2, "name": "slack_lab", "product_name": "Slack", "product_code": "slack"},
    ]

    with patch("environment_fix.fetch_configured_assets", return_value=configured):
        out = discover_suggested_defaults(None)
    assert out.get("okta") == "okta"
    assert out.get("slack") == "slack_lab"


def test_apply_environment_fixes_needs_confirm():
    configured = [
        {"id": 1, "name": "okta", "product_name": "Okta", "product_code": "okta"},
    ]
    cfg = {"asset_defaults": ""}

    with patch("environment_fix.fetch_configured_assets", return_value=configured):
        out = apply_environment_fixes_payload(object(), cfg, confirm=False)
    assert out["needs_confirm"] is True
    assert out["proposed_asset_defaults"]["okta"] == "okta"


@patch("environment_fix.persist_asset_defaults")
@patch("environment_fix.discover_suggested_defaults")
def test_apply_environment_fixes_applies(mock_discover, mock_persist):
    mock_discover.return_value = {"okta": "okta"}
    mock_persist.return_value = (True, "")
    cfg = {"asset_defaults": ""}
    out = apply_environment_fixes_payload(object(), cfg, confirm=True)
    assert out["status"] == "success"
    assert out["fixes_applied"]
    mock_persist.assert_called_once()
