"""Tests for visual preview enrichment."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from builder_helpers import SCAFFOLDS, preview_blocks_from_source
from preview_visual import attach_visual_preview


def test_attach_visual_preview_has_mermaid_and_storyboard():
    source = SCAFFOLDS["clearpass-quarantine"]
    preview = preview_blocks_from_source(source)
    payload = attach_visual_preview(
        {"status": "success", "source": source, "preview": preview},
        base_url="https://soar.example:8443",
    )
    assert payload.get("mermaid")
    assert "flowchart" in payload["mermaid"]
    assert len(payload.get("storyboard", [])) >= 3
    assert payload.get("preview_graph", {}).get("nodes")


def test_clearpass_preview_includes_named_actions():
    source = SCAFFOLDS["clearpass-quarantine"]
    preview = preview_blocks_from_source(source)
    action_blocks = [b for b in preview if b.get("type") == "action"]
    actions = [b.get("action") for b in action_blocks]
    assert "get endpoint" in actions
    assert "quarantine device" in actions
    collect_blocks = [b for b in preview if b.get("type") == "collect"]
    assert collect_blocks
    assert any("Source IP" in b.get("fields", "") for b in collect_blocks)
    decision_blocks = [b for b in preview if b.get("type") == "decision"]
    assert decision_blocks
    assert decision_blocks[0].get("summary")


def test_soar_links_in_payload():
    source = SCAFFOLDS["clearpass-quarantine"]
    preview = preview_blocks_from_source(source)
    payload = attach_visual_preview(
        {
            "status": "success",
            "source": source,
            "preview": preview,
            "playbook_id": 42,
            "playbook_name": "hello_world/hello_world",
            "playbook_search": "hello_world",
            "playbook_slug": "hello_world",
            "playbook_record": {"python_version": "3", "playbook_type": "automation"},
        },
        base_url="https://10.236.39.108:8443",
    )
    links = payload["soar_links"]
    # When playbook_id is known, open goes straight to VPE (not playbooks search).
    assert links["open"] == "https://10.236.39.108:8443/playbook/42?editor=visual"
    assert links["playbooks_search"] == "https://10.236.39.108:8443/playbooks?search=hello_world"
    assert links["python"] == "https://10.236.39.108:8443/playbook/42?editor=python"
    assert "42" in links["vpe"]
