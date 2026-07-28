"""Tests for organization template loading from asset config."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from builder_helpers import scaffold_pattern  # noqa: E402
from custom_templates import parse_org_templates  # noqa: E402
from ir.fixtures import smoke_ir_document  # noqa: E402
from pattern_catalog import list_patterns_payload  # noqa: E402

VALID_SOURCE = '''import phantom.app as phantom


def on_start(container):
    phantom.add_note(container=container, content="org template ran", title="Org")
    on_finish(container)


def on_finish(container):
    phantom.debug("done")
'''


def _strict_org_ir(template_id: str = "org-review-note"):
    document = copy.deepcopy(smoke_ir_document())
    document["id"] = template_id
    document["name"] = "Organization Review Note"
    document["metadata"]["template_id"] = template_id
    return document


def test_parse_valid_legacy_org_template_when_explicitly_enabled():
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
    reg = parse_org_templates(raw, allow_legacy_python=True)
    assert reg.count == 1
    assert not reg.errors
    assert "org-demo-note" in reg.scaffolds
    assert reg.template_kinds["org-demo-note"] == "legacy_python"


def test_legacy_python_is_ignored_by_default():
    reg = parse_org_templates(
        {
            "templates": [
                {
                    "id": "org-demo-note",
                    "label": "Org Demo",
                    "source": VALID_SOURCE,
                }
            ]
        }
    )
    assert reg.count == 0
    assert not reg.errors
    assert any("ignored" in warning for warning in reg.warnings)


def test_parse_strict_ir_template():
    reg = parse_org_templates(
        None,
        raw_ir_config={
            "schema_version": "1.0",
            "templates": [
                {
                    "id": "org-review-note",
                    "label": "Organization Review Note",
                    "tier": "safe",
                    "ir": _strict_org_ir(),
                }
            ],
        },
    )
    assert reg.count == 1
    assert not reg.errors
    assert reg.ir_for("org-review-note") is not None
    assert "org-review-note" not in reg.scaffolds
    assert reg.template_kinds["org-review-note"] == "ir"
    assert reg.catalog_rows[0]["trusted_ir"] is True


def test_strict_ir_id_and_metadata_must_match_wrapper():
    wrong_id = _strict_org_ir()
    wrong_id["id"] = "org-different-id"
    wrong_metadata = _strict_org_ir("org-review-two")
    wrong_metadata["metadata"]["template_id"] = "org-different-id"
    reg = parse_org_templates(
        None,
        raw_ir_config={
            "templates": [
                {
                    "id": "org-review-note",
                    "ir": wrong_id,
                },
                {
                    "id": "org-review-two",
                    "ir": wrong_metadata,
                },
            ]
        },
    )
    assert reg.count == 0
    assert any("ir.id must equal" in error for error in reg.errors)
    assert any(
        "metadata.template_id must equal" in error
        for error in reg.errors
    )


def test_duplicate_json_keys_and_nonfinite_values_fail_closed():
    duplicate = (
        '{"templates":[{"id":"org-review-note",'
        '"id":"org-shadowed","ir":{}}]}'
    )
    nonfinite = '{"templates":[],"value":NaN}'

    duplicate_reg = parse_org_templates(None, raw_ir_config=duplicate)
    nonfinite_reg = parse_org_templates(None, raw_ir_config=nonfinite)

    assert any(
        "duplicate JSON key" in error for error in duplicate_reg.errors
    )
    assert any(
        "non-finite JSON number" in error
        for error in nonfinite_reg.errors
    )


def test_oversized_org_metadata_is_rejected():
    reg = parse_org_templates(
        None,
        raw_ir_config={
            "templates": [
                {
                    "id": "org-review-note",
                    "label": "x" * 257,
                    "ir": _strict_org_ir(),
                }
            ]
        },
    )
    assert reg.count == 0
    assert any("label exceeds" in error for error in reg.errors)


def test_reject_non_org_prefix():
    reg = parse_org_templates(
        {
            "templates": [
                {
                    "id": "hello-override",
                    "source": VALID_SOURCE,
                    "label": "Bad",
                }
            ]
        },
        allow_legacy_python=True,
    )
    assert reg.count == 0
    assert any("org-" in error for error in reg.errors)


def test_scaffold_legacy_org_template_only_when_enabled():
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
        },
        allow_legacy_python=True,
    )
    result = scaffold_pattern("org-demo-note", org_registry=reg)
    assert result.get("status") == "success"
    assert "org template ran" in result.get("source", "")


def test_list_patterns_includes_strict_org_and_diagnostics():
    reg = parse_org_templates(
        {
            "templates": [
                {
                    "id": "org-legacy-note",
                    "source": VALID_SOURCE,
                }
            ]
        },
        raw_ir_config={
            "templates": [
                {
                    "id": "org-review-note",
                    "label": "Org Demo",
                    "tier": "safe",
                    "ir": _strict_org_ir(),
                }
            ]
        },
    )
    payload = list_patterns_payload(org_registry=reg)
    ids = {row["id"] for row in payload["patterns"]}
    assert "org-review-note" in ids
    assert "org-legacy-note" not in ids
    assert payload.get("org_template_count") == 1
    assert "Organization" in payload.get("by_category", {})
    strict = next(
        row
        for row in payload["patterns"]
        if row["id"] == "org-review-note"
    )
    assert strict["trusted_ir"] is True
    assert strict["template_kind"] == "ir"
    assert payload["org_warnings"]
