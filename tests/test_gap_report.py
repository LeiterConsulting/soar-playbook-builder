"""GapReport schema, ordering, determinism, and rendering tests."""

from __future__ import annotations

import copy
import hashlib
import ast
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))
GOLDEN_ASSET_UNBOUND = (
    Path(__file__).resolve().parent
    / "golden"
    / "gap_report_asset_unbound.sha256"
)

from ir.schema import PlaybookIR  # noqa: E402
from validate import gap_report_json_schema, preflight  # noqa: E402
from validate.fixtures import (  # noqa: E402
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
    qualified_smoke_ir,
)
from validate.render import render_gap_report  # noqa: E402
from validate.report import PREFLIGHT_GAP_IDS, SUPPORTED_GAP_IDS  # noqa: E402


def test_gap_report_schema_accepts_ok_and_blocked_reports():
    ok = preflight(
        qualified_smoke_ir(),
        qualified_smoke_index(),
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    jsonschema.Draft202012Validator(gap_report_json_schema()).validate(ok.to_dict())

    document = qualified_smoke_document()
    action = next(node for node in document["nodes"] if node["type"] == "action")
    action["asset"] = {"kind": "asset_unbound"}
    blocked = preflight(
        PlaybookIR.from_dict(document),
        qualified_smoke_index(),
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    jsonschema.Draft202012Validator(gap_report_json_schema()).validate(
        blocked.to_dict()
    )
    assert blocked.status == "blocked"
    assert hashlib.sha256(blocked.canonical_json().encode("utf-8")).hexdigest() == (
        GOLDEN_ASSET_UNBOUND.read_text(encoding="utf-8").strip()
    )


def test_report_is_deterministic_and_gap_order_is_stable():
    document = qualified_smoke_document()
    action = next(node for node in document["nodes"] if node["type"] == "action")
    action["asset"] = {"kind": "asset_unbound"}
    index = qualified_smoke_index()
    index.harvest_status = "partial"
    index.harvest_errors = ["z-error", "a-error"]
    first = preflight(
        PlaybookIR.from_dict(document),
        index,
        evaluated_at=FIXTURE_EVALUATED_AT,
    )

    reordered = copy.deepcopy(index)
    reordered.assets = list(reversed(reordered.assets))
    reordered.apps = dict(reversed(list(reordered.apps.items())))
    reordered.harvest_errors = list(reversed(reordered.harvest_errors))
    second = preflight(
        PlaybookIR.from_dict(document),
        reordered,
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    assert first.canonical_json() == second.canonical_json()
    assert [gap.id for gap in first.gaps] == [
        "ASSET_UNBOUND",
        "INDEX_HARVEST_DEGRADED",
    ]


def test_renderer_uses_only_report_entities():
    document = qualified_smoke_document()
    action = next(node for node in document["nodes"] if node["type"] == "action")
    action["asset"] = {"kind": "asset_unbound"}
    report = preflight(
        PlaybookIR.from_dict(document),
        qualified_smoke_index(),
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    rendered = render_gap_report(report)
    assert "ASSET_UNBOUND" in rendered
    assert "lookup_user" in rendered
    assert "okta" in rendered
    assert "install a random connector" not in rendered.lower()
    assert rendered == render_gap_report(report)
    json.loads(report.canonical_json())


def test_every_rule_gap_id_is_closed_and_has_explicit_remediation():
    emitted: set[str] = set()
    rules_dir = ROOT / "validate" / "rules"
    for path in rules_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "gap_id"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    emitted.add(keyword.value.value)
    assert emitted == set(PREFLIGHT_GAP_IDS)

    remediation_tree = ast.parse(
        (ROOT / "validate" / "remediation.py").read_text(encoding="utf-8")
    )
    remediation_ids: set[str] = set()
    for node in ast.walk(remediation_tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
            remediation_ids.update(
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    assert remediation_ids == set(SUPPORTED_GAP_IDS)
