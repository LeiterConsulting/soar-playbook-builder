"""Vet every template: scaffold, Python, COA, assets, keyword routing."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from asset_resolver import extract_required_asset_keys  # noqa: E402
from builder_helpers import SCAFFOLDS, analyze_playbook, scaffold_pattern  # noqa: E402
from coa_builder import build_modern_playbook_json  # noqa: E402
from local_nl_build import match_pattern  # noqa: E402
from pattern_catalog import catalog_ids  # noqa: E402
from preview_visual import extract_phantom_acts_with_context  # noqa: E402


def _action_functions_in_source(source: str) -> set[str]:
    funcs = {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)}
    return funcs


def _coa_action_func_names(meta: dict) -> list[str]:
    nodes = meta.get("coa", {}).get("data", {}).get("nodes", {})
    return [
        n["data"]["functionName"]
        for n in nodes.values()
        if n.get("type") == "action" and n.get("data", {}).get("functionName")
    ]


def test_catalog_matches_scaffolds():
    for pid in catalog_ids():
        assert pid in SCAFFOLDS, f"catalog id {pid!r} missing from SCAFFOLDS"


def test_every_scaffold_loads():
    for pid in catalog_ids():
        result = scaffold_pattern(pid)
        assert result.get("status") == "success", f"{pid}: {result.get('error')}"
        assert result.get("source"), f"{pid}: empty source"
        assert result.get("preview"), f"{pid}: empty preview"


def test_every_scaffold_valid_python_and_coa():
    for pid in catalog_ids():
        source = SCAFFOLDS[pid]
        analysis = analyze_playbook(source)
        assert analysis["valid_python"], f"{pid}: invalid python"
        assert analysis["score"] >= 75, f"{pid}: score {analysis['score']}"
        assert "on_start" in analysis["functions"], f"{pid}: missing on_start"

        meta = build_modern_playbook_json(source, pid, pattern=pid)
        json.dumps(meta)
        node_types = {n.get("type") for n in meta["coa"]["data"]["nodes"].values()}
        assert "filter" not in node_types, f"{pid}: COA has filter nodes"
        assert "start" in node_types and "end" in node_types

        coa_funcs = _coa_action_func_names(meta)
        source_funcs = _action_functions_in_source(source)
        for fn in coa_funcs:
            assert fn in source_funcs, f"{pid}: COA action {fn!r} not in source"


def test_phantom_act_callbacks_named():
    """Each phantom.act callback= should reference an existing function."""
    for pid in catalog_ids():
        source = SCAFFOLDS[pid]
        funcs = _action_functions_in_source(source)
        for act in extract_phantom_acts_with_context(source):
            cb = act.get("callback")
            if cb and cb not in ("None", "on_finish"):
                assert cb in funcs, f"{pid}: callback {cb!r} missing"


def test_asset_keys_have_hints():
    from asset_resolver import ASSET_TYPE_HINTS  # noqa: E402

    for pid in catalog_ids():
        for key in extract_required_asset_keys(SCAFFOLDS[pid]):
            if key == "soar":
                continue
            assert key in ASSET_TYPE_HINTS, f"{pid}: asset key {key!r} has no resolver hint"


def test_keyword_routes_for_catalog():
    samples = {
        "failed-logins-okta": "build failed logins okta playbook",
        "virustotal-enrichment": "build virustotal file hash playbook",
        "panw-block-ip": "build palo alto block ip playbook",
        "clearpass-quarantine": "build clearpass quarantine playbook",
        "servicenow-incident": "build servicenow p1 incident playbook",
    }
    for expected, msg in samples.items():
        got = match_pattern(msg)
        assert got == expected, f"expected {expected} got {got} for {msg!r}"


def test_virustotal_closes_on_malicious():
    source = SCAFFOLDS["virustotal-enrichment"]
    funcs = _action_functions_in_source(source)
    assert "decision_verdict" in funcs
    assert "close_malicious_container" in funcs
    assert "VT_MALICIOUS_THRESHOLD" in source
    assert "phantom.set_status" in source
    assert "callback=decision_verdict" in source
    assert "action_vt_query:action_result.summary.malicious" in source


if __name__ == "__main__":
    test_catalog_matches_scaffolds()
    test_every_scaffold_loads()
    test_every_scaffold_valid_python_and_coa()
    test_phantom_act_callbacks_named()
    test_asset_keys_have_hints()
    test_virustotal_closes_on_malicious()
    print(f"ok — vetted {len(catalog_ids())} templates")
