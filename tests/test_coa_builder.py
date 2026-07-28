"""Tests for modern COA packaging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from builder_helpers import SCAFFOLDS  # noqa: E402
from coa_builder import build_modern_playbook_json  # noqa: E402


def test_modern_json_has_coa_nodes():
    source = SCAFFOLDS["hello"]
    meta = build_modern_playbook_json(source, "Hello World", pattern="hello")
    assert "coa" in meta
    coa = meta["coa"]
    assert coa["python_version"] == "3.13"
    nodes = coa["data"]["nodes"]
    edges = coa["data"]["edges"]
    assert len(nodes) >= 2
    assert len(edges) >= 1
    types = {n.get("type") for n in nodes.values()}
    assert "start" in types
    assert "end" in types


def test_servicenow_has_action_nodes():
    source = SCAFFOLDS["servicenow-incident"]
    meta = build_modern_playbook_json(source, "ServiceNow P1", pattern="servicenow-incident")
    nodes = meta["coa"]["data"]["nodes"]
    node_types = [n.get("type") for n in nodes.values()]
    assert "action" in node_types
    assert "filter" not in node_types


def test_json_serializable():
    source = SCAFFOLDS["hello"]
    meta = build_modern_playbook_json(source, "Hello World")
    json.dumps(meta)


def test_okta_coa_matches_python_functions():
    source = SCAFFOLDS["okta-idp-response"]
    meta = build_modern_playbook_json(source, "Okta IDP", pattern="okta-idp-response")
    nodes = meta["coa"]["data"]["nodes"]
    node_types = [n.get("type") for n in nodes.values()]
    assert "filter" not in node_types
    action_funcs = [
        n["data"]["functionName"]
        for n in nodes.values()
        if n.get("type") == "action"
    ]
    assert action_funcs == [
        "lookup_okta_user",
        "remediate_okta_user",
        "disable_okta_user",
    ]


if __name__ == "__main__":
    test_modern_json_has_coa_nodes()
    test_servicenow_has_action_nodes()
    test_okta_coa_matches_python_functions()
    test_json_serializable()
    print("ok")
