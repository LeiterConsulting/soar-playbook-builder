"""Build Splunk SOAR modern (visual) playbook JSON with embedded COA graph."""

from __future__ import annotations

import re
from typing import Any

from draft_import import BUILDER_LABEL, DEFAULT_PLAYBOOK_PYTHON_VERSION, slug_from_label
from preview_visual import extract_phantom_acts, extract_phantom_acts_with_context

COA_SCHEMA = "5.0.23"
COA_VERSION = "7.1.1.41"
DEFAULT_CATEGORY = "Use Cases"
DEFAULT_TRIGGER = "container_started"
PHANTOM_CONNECTOR = "Splunk SOAR"
# Callback-style Python playbooks: COA is illustrative — skip synthetic filter/decision nodes.
COA_SKIP_BLOCK_TYPES = frozenset({"collect", "decision"})
BUILTIN_PHANTOM_ACTIONS = frozenset({
    "add note",
    "assign",
    "add artifact",
    "add listitem",
    "update artifact",
    "set status",
    "pin container",
    "unpin container",
})


def _empty_node_shell(nid: str, ntype: str, y: int) -> dict[str, Any]:
    return {
        "id": nid,
        "type": ntype,
        "x": 20.0,
        "y": float(y),
        "errors": {},
        "warnings": {},
    }


def _start_node(nid: str, func_id: int, y: int) -> dict[str, Any]:
    node = _empty_node_shell(nid, "start", y)
    node["data"] = {
        "advanced": {"join": []},
        "functionName": "on_start",
        "id": nid,
        "type": "start",
        "functionId": func_id,
    }
    return node


def _end_node(nid: str, func_id: int, y: int) -> dict[str, Any]:
    node = _empty_node_shell(nid, "end", y)
    node["data"] = {
        "advanced": {"join": []},
        "functionName": "on_finish",
        "id": nid,
        "type": "end",
        "functionId": func_id,
    }
    return node


def _collect_node(
    nid: str,
    func_id: int,
    y: int,
    datapaths: str,
    func_name: str,
) -> dict[str, Any]:
    """Collect steps map to filter blocks in the VPE."""
    paths = [p.strip() for p in datapaths.split(",") if p.strip()]
    comparisons: list[dict[str, Any]] = []
    for idx, path in enumerate(paths[:4]):
        comparisons.append(
            {
                "conditionIndex": 0,
                "op": "!=",
                "param": path,
                "value": "",
                "comparisonKey": f"comparison_key_{idx}",
            }
        )
    node = _empty_node_shell(nid, "filter", y)
    node["data"] = {
        "advanced": {
            "customName": func_name.replace("_", " "),
            "customNameId": 0,
            "delimiter": ",",
            "delimiter_enabled": True,
            "description": f"Collect: {datapaths}",
            "join": [],
            "note": f"Collect datapaths: {datapaths}",
        },
        "conditions": [
            {
                "comparisons": comparisons or [{"op": "!=", "param": "container:id", "value": ""}],
                "conditionIndex": 0,
                "conditionKey": f"condition_{nid}",
                "customName": "collect",
                "logic": "and",
            }
        ],
        "functionId": func_id,
        "functionName": func_name,
        "id": nid,
        "type": "filter",
    }
    return node


def _action_node(
    nid: str,
    func_id: int,
    y: int,
    action_name: str,
    asset: str,
    func_name: str,
) -> dict[str, Any]:
    asset_key = (asset or "soar").strip()
    action_lower = (action_name or "").lower()
    use_phantom = asset_key == "soar" or action_lower in BUILTIN_PHANTOM_ACTIONS
    connector = PHANTOM_CONNECTOR if use_phantom else asset_key.replace("_", " ").replace("-", " ").title()
    node = _empty_node_shell(nid, "action", y)
    node["data"] = {
        "action": action_name,
        "actionType": "generic",
        "advanced": {
            "customName": action_name,
            "customNameId": 0,
            "description": action_name,
            "join": [],
            "note": action_name,
        },
        "connector": connector,
        "connectorConfigs": [asset_key],
        "functionId": func_id,
        "functionName": func_name,
        "id": nid,
        "parameters": {},
        "requiredParameters": [],
        "type": "action",
    }
    return node


def _decision_node(nid: str, func_id: int, y: int, detail: str, func_name: str) -> dict[str, Any]:
    node = _empty_node_shell(nid, "filter", y)
    node["data"] = {
        "advanced": {
            "customName": "decision",
            "customNameId": 0,
            "description": detail,
            "join": [],
            "note": detail,
        },
        "conditions": [
            {
                "comparisons": [{"op": "==", "param": "container:id", "value": ""}],
                "conditionIndex": 0,
                "conditionKey": f"condition_{nid}",
                "customName": "branch",
                "logic": "and",
            }
        ],
        "functionId": func_id,
        "functionName": func_name,
        "id": nid,
        "type": "filter",
    }
    return node


def _edge(source: str, target: str) -> dict[str, str]:
    return {
        "id": f"port_{source}_to_port_{target}",
        "sourceNode": source,
        "sourcePort": f"{source}_out",
        "targetNode": target,
        "targetPort": f"{target}_in",
    }


def build_coa_from_preview(
    source: str,
    preview_blocks: list[dict[str, str]],
    *,
    asset_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert sidecar preview blocks into SOAR COA nodes + edges."""
    acts = extract_phantom_acts_with_context(source)
    act_idx = 0
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    prev_id: str | None = None
    func_id = 1
    y = 0
    node_num = 0

    def add_node(node: dict[str, Any]) -> str:
        nonlocal prev_id, node_num, y
        nid = str(node_num)
        node_num += 1
        node["id"] = nid
        if "data" in node and isinstance(node["data"], dict):
            node["data"]["id"] = nid
        nodes[nid] = node
        if prev_id is not None:
            edges.append(_edge(prev_id, nid))
        prev_id = nid
        y += 140
        return nid

    for block in preview_blocks:
        btype = block.get("type", "action")
        detail = block.get("detail") or block.get("label") or ""
        if btype in COA_SKIP_BLOCK_TYPES:
            continue
        if btype == "start":
            add_node(_start_node("0", func_id, y))
            func_id += 1
            continue
        if btype == "end":
            add_node(_end_node("0", func_id, y))
            func_id += 1
            continue
        if btype == "collect":
            continue
        if btype == "decision":
            continue
        if btype == "action":
            act = acts[act_idx] if act_idx < len(acts) else {}
            act_idx += 1
            action_name = act.get("action") or detail or "action"
            asset = act.get("assets", [""])[0] if act.get("assets") else "soar"
            configured_asset = (asset_map or {}).get(asset, asset)
            fname = act.get("function") or act.get("name") or re.sub(
                r"[^a-z0-9_]", "_", action_name.lower()
            )[:40]
            add_node(_action_node("0", func_id, y, action_name, configured_asset, fname))
            func_id += 1

    if not nodes:
        add_node(_start_node("0", 1, 0))
        add_node(_end_node("0", 2, 140))

    return {
        "schema": COA_SCHEMA,
        "version": COA_VERSION,
        "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION,
        "playbook_type": "automation",
        "playbook_trigger": DEFAULT_TRIGGER,
        "input_spec": None,
        "output_spec": None,
        "data": {
            "description": "Playbook Builder modern import",
            "edges": edges,
            "globalCustomCode": "",
            "hash": "",
            "notes": "",
            "nodes": nodes,
        },
    }


def build_modern_playbook_json(
    source: str,
    display_name: str,
    *,
    pattern: str | None = None,
    preview_blocks: list[dict[str, str]] | None = None,
    labels: list[str] | None = None,
    asset_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Full ``.json`` sidecar for modern/visual SOAR import (COA embedded)."""
    from builder_helpers import preview_blocks_from_source

    name = (display_name or "NL Draft Playbook").strip()
    slug = slug_from_label(name)
    blocks = preview_blocks if preview_blocks is not None else preview_blocks_from_source(source)
    tag_labels = list(labels or [])
    for tag in (BUILDER_LABEL, slug.replace("-", "_")):
        if tag not in tag_labels:
            tag_labels.append(tag)
    if pattern and pattern.replace("-", "_") not in tag_labels:
        tag_labels.append(pattern.replace("-", "_"))

    return {
        "blockly": False,
        "blockly_xml": "<xml/>",
        "category": DEFAULT_CATEGORY,
        "coa": build_coa_from_preview(source, blocks, asset_map=asset_map),
        "draft_mode": False,
        "labels": tag_labels[:8],
        "tags": tag_labels[:8],
        "name": name,
        "description": f"Created by SOAR Playbook Builder — {name}",
        "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION,
        "playbook_type": "automation",
    }
