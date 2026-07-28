"""Tests for ES back-link URL building."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from es_links import attach_es_links, build_mission_control_url  # noqa: E402


def test_mission_control_with_event():
    url = build_mission_control_url("https://es:8000/", event_id="abc-123")
    assert "ess_investigation" in url
    assert "event_id=abc-123" in url


def test_attach_es_links():
    ctx: dict = {"event_id": "x1", "rule_name": "Failed Logins"}
    attach_es_links(ctx, "https://es.lab:8000")
    assert ctx.get("es_back_url")
    assert "x1" in ctx["es_back_url"]


if __name__ == "__main__":
    test_mission_control_with_event()
    test_attach_es_links()
    print("ok")
