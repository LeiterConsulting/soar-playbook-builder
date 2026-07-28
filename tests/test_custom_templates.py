"""Tests for organization template loading from asset config."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from custom_templates import parse_org_templates  # noqa: E402
from builder_helpers import scaffold_pattern  # noqa: E402
from pattern_catalog import list_patterns_payload  # noqa: E402

VALID_SOURCE = '''import phantom.app as phantom


def on_start(container):
    phantom.add_note(container=container, content="org template ran", title="Org")
    on_finish(container)


def on_finish(container):
    phantom.debug("done")
'''


def test_parse_valid_org_template():
    raw = {
        "templates": [
            {
                "id": "org-demo-note",
                "label": "Org Demo Note",
                "category": "Organization",
                "tier": "safe",
                "source": VALID_SOURCE,
                "nl_keywords": ["org demo", "custom note"],
            }
        ]
    }
    reg = parse_org_templates(raw)
    assert reg.count == 1
    assert not reg.errors
    assert "org-demo-note" in reg.scaffolds


def test_reject_non_org_prefix():
    reg = parse_org_templates(
        {"templates": [{"id": "hello-override", "source": VALID_SOURCE, "label": "Bad"}]}
    )
    assert reg.count == 0
    assert any("org-" in e for e in reg.errors)


def test_scaffold_org_template():
    reg = parse_org_templates(
        {
            "templates": [
                {
                    "id": "org-demo-note",
                    "label": "Org Demo",
                    "source": VALID_SOURCE,
                    "tier": "safe",
                }
            ]
        }
    )
    result = scaffold_pattern("org-demo-note", org_registry=reg)
    assert result.get("status") == "success"
    assert "org template ran" in result.get("source", "")


def test_list_patterns_includes_org():
    reg = parse_org_templates(
        {
            "templates": [
                {
                    "id": "org-demo-note",
                    "label": "Org Demo",
                    "source": VALID_SOURCE,
                    "tier": "safe",
                }
            ]
        }
    )
    payload = list_patterns_payload(org_registry=reg)
    ids = {p["id"] for p in payload["patterns"]}
    assert "org-demo-note" in ids
    assert payload.get("org_template_count") == 1
    assert "Organization" in payload.get("by_category", {})


if __name__ == "__main__":
    test_parse_valid_org_template()
    test_reject_non_org_prefix()
    test_scaffold_org_template()
    test_list_patterns_includes_org()
    print("ok")
