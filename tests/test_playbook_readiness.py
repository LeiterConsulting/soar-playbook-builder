"""Tests for playbook readiness checks and auto-fix."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from playbook_readiness import (  # noqa: E402
    apply_readiness_fixes,
    build_readiness_report,
)

HOLLOW = '''import phantom.app as phantom

def on_start(container):
    sev = container.get("severity")
    if sev == "high":
        phantom.add_note(container=container, content="alert", title="x")
    on_finish(container)

def on_finish(container):
    phantom.debug("done")
'''

SLACK = '''import phantom.app as phantom

SLACK_CHANNEL = "#your-channel"

def on_start(container):
    phantom.act(
        "send message",
        parameters=[{"destination": SLACK_CHANNEL, "message": "hi"}],
        assets=["slack"],
        callback=on_finish,
        name="action_slack",
        container=container,
    )

def on_finish(container):
    phantom.debug("done")
'''


def test_hollow_playbook_flags_no_act():
    report = build_readiness_report(HOLLOW, request=None, cfg={})
    ids = {i["id"] for i in report["items"]}
    assert "no_phantom_act" in ids
    assert not report["ready_for_import"]


def test_apply_constants_and_assets():
    report = build_readiness_report(
        SLACK,
        request=None,
        cfg={
            "asset_defaults": {"slack": "slack_lab"},
            "playbook_defaults_json": '{"constants": {"SLACK_CHANNEL": "#soc-alerts"}}',
        },
    )
    fixed, applied = apply_readiness_fixes(SLACK, report, cfg={
        "asset_defaults": {"slack": "slack_lab"},
        "playbook_defaults_json": '{"constants": {"SLACK_CHANNEL": "#soc-alerts"}}',
    }, fix_ids=["map_assets", "apply_constants"])
    assert 'assets=["slack_lab"]' in fixed
    assert 'SLACK_CHANNEL = "#soc-alerts"' in fixed
    assert len(applied) >= 1


if __name__ == "__main__":
    test_hollow_playbook_flags_no_act()
    test_apply_constants_and_assets()
    print("ok")
