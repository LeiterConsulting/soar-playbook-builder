"""Render deterministic visual-playbook JSON directly from IR.

The envelope preserves the repository's current COA shape for offline tooling.
Exact Visual Playbook Editor import fidelity remains a live-SOAR qualification
item and is therefore declared in artifact metadata rather than assumed.
"""

from __future__ import annotations

from typing import Any

from coa_builder import (
    COA_SCHEMA,
    COA_VERSION,
    DEFAULT_CATEGORY,
    DEFAULT_PLAYBOOK_PYTHON_VERSION,
    DEFAULT_TRIGGER,
)
from ir.schema import (
    ActionNode,
    CodeNode,
    ComparisonCondition,
    Condition,
    DecisionNode,
    EndNode,
    FilterNode,
    FormatNode,
    GroupCondition,
    JoinNode,
    NotCondition,
    PlaybookIR,
    PromptNode,
    StartNode,
    UnaryCondition,
)

from .datapath import action_block_name, compile_binding

_OPERATOR_TEXT = {
    "eq": "==",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "contains": "contains",
    "starts_with": "starts_with",
    "ends_with": "ends_with",
    "in": "in",
    "exists": "exists",
    "not_exists": "not_exists",
}


def _outbound(node: Any) -> list[tuple[str, str]]:
    if isinstance(node, StartNode | FormatNode | JoinNode):
        return [("next", node.next)]
    if isinstance(node, ActionNode | CodeNode):
        return [("success", node.on_success), ("failure", node.on_failure)]
    if isinstance(node, DecisionNode):
        return [("true", node.on_true), ("false", node.on_false)]
    if isinstance(node, FilterNode):
        return [("match", node.on_match), ("no_match", node.on_no_match)]
    if isinstance(node, PromptNode):
        edges = [("success", node.on_success), ("failure", node.on_failure)]
        if node.on_timeout:
            edges.append(("timeout", node.on_timeout))
        return edges
    return []


def _layout(ir: PlaybookIR) -> dict[str, tuple[float, float]]:
    by_id = {node.id: node for node in ir.nodes}
    incoming = {node_id: 0 for node_id in by_id}
    targets: dict[str, list[str]] = {}
    for node in ir.nodes:
        targets[node.id] = [target for _, target in _outbound(node)]
        for target in targets[node.id]:
            incoming[target] += 1
    ready = sorted(node_id for node_id, count in incoming.items() if count == 0)
    levels = {node_id: 0 for node_id in ready}
    while ready:
        source = ready.pop(0)
        for target in targets[source]:
            levels[target] = max(levels.get(target, 0), levels[source] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    grouped: dict[int, list[str]] = {}
    for node_id in sorted(by_id):
        grouped.setdefault(levels.get(node_id, 0), []).append(node_id)
    positions: dict[str, tuple[float, float]] = {}
    for level, node_ids in grouped.items():
        width = len(node_ids)
        for index, node_id in enumerate(node_ids):
            x = (index - (width - 1) / 2) * 340.0 + 500.0
            positions[node_id] = (x, level * 160.0)
    return positions


def _binding_payload(binding: Any, nodes_by_id: dict[str, Any]) -> dict[str, Any]:
    return compile_binding(binding, nodes_by_id=nodes_by_id).to_dict()


def _condition_payload(
    condition: Condition,
    nodes_by_id: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(condition, ComparisonCondition):
        return {
            "op": condition.op,
            "operator": _OPERATOR_TEXT[condition.op],
            "left": _binding_payload(condition.left, nodes_by_id),
            "right": _binding_payload(condition.right, nodes_by_id),
        }
    if isinstance(condition, UnaryCondition):
        return {
            "op": condition.op,
            "operator": _OPERATOR_TEXT[condition.op],
            "value": _binding_payload(condition.value, nodes_by_id),
        }
    if isinstance(condition, GroupCondition):
        return {
            "op": condition.op,
            "conditions": [
                _condition_payload(child, nodes_by_id)
                for child in condition.conditions
            ],
        }
    if isinstance(condition, NotCondition):
        return {
            "op": "not",
            "condition": _condition_payload(condition.condition, nodes_by_id),
        }
    raise TypeError(f"unsupported condition: {type(condition).__name__}")


def _base_node(
    *,
    native_id: str,
    node: Any,
    function_id: int,
    position: tuple[float, float],
    native_type: str | None = None,
) -> dict[str, Any]:
    node_type = native_type or node.type
    function_name = (
        "on_start"
        if isinstance(node, StartNode)
        else "on_finish"
        if isinstance(node, EndNode)
        else action_block_name(node.id)
    )
    return {
        "id": native_id,
        "type": node_type,
        "x": position[0],
        "y": position[1],
        "errors": {},
        "warnings": {},
        "data": {
            "advanced": {
                "customName": node.label or node.id.replace("_", " "),
                "customNameId": 0,
                "description": node.label or node.id,
                "join": [],
                "note": f"IR node {node.id} ({node.type})",
            },
            "builderIrNodeId": node.id,
            "builderNodeType": node.type,
            "functionId": function_id,
            "functionName": function_name,
            "id": native_id,
            "type": node_type,
        },
    }


def _visual_node(
    *,
    native_id: str,
    node: Any,
    function_id: int,
    position: tuple[float, float],
    nodes_by_id: dict[str, Any],
) -> dict[str, Any]:
    native_type = (
        "filter" if isinstance(node, DecisionNode | FilterNode) else node.type
    )
    output = _base_node(
        native_id=native_id,
        node=node,
        function_id=function_id,
        position=position,
        native_type=native_type,
    )
    data = output["data"]
    if isinstance(node, ActionNode):
        data.update(
            {
                "action": node.action,
                "actionType": "generic",
                "app": node.app,
                "connector": node.app.replace("_", " ").replace("-", " ").title(),
                "connectorConfigs": (
                    [node.asset.name] if node.asset.kind == "asset" else []
                ),
                "parameters": {
                    key: _binding_payload(binding, nodes_by_id)
                    for key, binding in node.parameters
                },
                "requiredParameters": [],
            }
        )
        if node.asset.kind != "asset":
            output["warnings"]["asset"] = "asset_unbound"
    elif isinstance(node, DecisionNode | FilterNode):
        expression = _condition_payload(node.condition, nodes_by_id)
        data["conditions"] = [
            {
                "builderExpression": expression,
                "comparisons": [],
                "conditionIndex": 0,
                "conditionKey": f"condition_{node.id}",
                "customName": node.label or node.id,
                "logic": "and",
            }
        ]
    elif isinstance(node, FormatNode):
        data.update(
            {
                "template": node.template,
                "inputs": {
                    key: _binding_payload(binding, nodes_by_id)
                    for key, binding in node.inputs
                },
                "output": node.output,
            }
        )
    elif isinstance(node, CodeNode):
        data.update(
            {
                "helper": node.helper,
                "arguments": {
                    key: _binding_payload(binding, nodes_by_id)
                    for key, binding in node.arguments
                },
                "output": node.output,
            }
        )
    elif isinstance(node, PromptNode):
        data.update(
            {
                "message": node.message,
                "responseKey": node.response_key,
                "responseTypes": [
                    {
                        "prompt": node.message,
                        "options": {
                            "type": "list",
                            "choices": list(node.choices),
                        },
                    }
                ],
                "respondInMinutes": 30,
                "role": "Automation",
            }
        )
    elif isinstance(node, JoinNode):
        data["strategy"] = node.strategy
    elif isinstance(node, EndNode):
        data["outcome"] = node.outcome
    return output


def render_visual(
    ir: PlaybookIR,
    *,
    compiler_version: str,
    artifact_schema_version: str,
) -> dict[str, Any]:
    """Return a deterministic visual artifact with a lossless IR envelope."""
    nodes_by_id = {node.id: node for node in ir.nodes}
    positions = _layout(ir)
    ordered = sorted(ir.nodes, key=lambda node: node.id)
    native_ids = {node.id: str(index) for index, node in enumerate(ordered)}
    nodes = {
        native_ids[node.id]: _visual_node(
            native_id=native_ids[node.id],
            node=node,
            function_id=index + 1,
            position=positions[node.id],
            nodes_by_id=nodes_by_id,
        )
        for index, node in enumerate(ordered)
    }
    edges: list[dict[str, Any]] = []
    for node in ordered:
        source = native_ids[node.id]
        for semantic, target_id in _outbound(node):
            target = native_ids[target_id]
            edges.append(
                {
                    "id": f"port_{source}_{semantic}_to_port_{target}",
                    "sourceNode": source,
                    "sourcePort": f"{source}_{semantic}_out",
                    "targetNode": target,
                    "targetPort": f"{target}_in",
                    "builderSemantic": semantic,
                    "builderSourceIrNode": node.id,
                    "builderTargetIrNode": target_id,
                }
            )
    labels = list(ir.metadata.labels)
    for label in ("playbook_builder", ir.id.replace("-", "_")):
        if label not in labels:
            labels.append(label)
    generated_at = ir.metadata.generated_at or "unspecified"
    return {
        "blockly": False,
        "blockly_xml": "<xml/>",
        "category": DEFAULT_CATEGORY,
        "coa": {
            "schema": COA_SCHEMA,
            "version": COA_VERSION,
            "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION,
            "playbook_type": "automation",
            "playbook_trigger": DEFAULT_TRIGGER,
            "input_spec": None,
            "output_spec": None,
            "data": {
                "description": ir.description,
                "edges": edges,
                "globalCustomCode": "",
                "hash": ir.sha256(),
                "notes": (
                    "Generated from Playbook Builder IR. Native editor fidelity "
                    "requires qualification against the target SOAR version."
                ),
                "nodes": nodes,
            },
        },
        "description": ir.description,
        "draft_mode": False,
        "labels": labels[:32],
        "name": ir.name,
        "playbook_builder": {
            "artifact_schema_version": artifact_schema_version,
            "capability_index_version": ir.metadata.capability_index_version,
            "compiler_version": compiler_version,
            "generated_at": generated_at,
            "ir": ir.to_dict(canonical=True),
            "ir_sha256": ir.sha256(),
            "model": ir.metadata.model or "none",
            "native_schema_status": "unverified_without_live_soar",
            "node_inventory": [node.id for node in ordered],
            "prompt_version": ir.metadata.prompt_version or "none",
        },
        "playbook_type": "automation",
        "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION,
        "tags": labels[:32],
    }
