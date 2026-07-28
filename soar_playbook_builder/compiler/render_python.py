"""Deterministically render validated IR as a Splunk SOAR Python playbook."""

from __future__ import annotations

import base64
import json
from typing import Any

from ir.schema import (
    ActionNode,
    CodeNode,
    ComparisonCondition,
    Condition,
    DecisionNode,
    FilterNode,
    FormatNode,
    GroupCondition,
    NotCondition,
    PlaybookIR,
    PromptNode,
    UnaryCondition,
    node_edges,
)

from .datapath import compile_binding


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _compiled_condition(
    condition: Condition,
    *,
    nodes_by_id: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(condition, ComparisonCondition):
        return {
            "op": condition.op,
            "left": compile_binding(
                condition.left,
                nodes_by_id=nodes_by_id,
            ).to_dict(),
            "right": compile_binding(
                condition.right,
                nodes_by_id=nodes_by_id,
            ).to_dict(),
        }
    if isinstance(condition, UnaryCondition):
        return {
            "op": condition.op,
            "value": compile_binding(
                condition.value,
                nodes_by_id=nodes_by_id,
            ).to_dict(),
        }
    if isinstance(condition, GroupCondition):
        return {
            "op": condition.op,
            "conditions": [
                _compiled_condition(child, nodes_by_id=nodes_by_id)
                for child in condition.conditions
            ],
        }
    if isinstance(condition, NotCondition):
        return {
            "op": "not",
            "condition": _compiled_condition(
                condition.condition,
                nodes_by_id=nodes_by_id,
            ),
        }
    raise TypeError(f"unsupported condition: {type(condition).__name__}")


def _runtime_contract(ir: PlaybookIR) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    nodes_by_id = {node.id: node for node in ir.nodes}
    bindings: dict[str, Any] = {}
    conditions: dict[str, Any] = {}
    parents: dict[str, list[str]] = {node.id: [] for node in ir.nodes}
    for node in ir.nodes:
        for target in node_edges(node):
            parents[target].append(node.id)
        rows = ()
        if isinstance(node, ActionNode):
            rows = node.parameters
        elif isinstance(node, FormatNode):
            rows = node.inputs
        elif isinstance(node, CodeNode):
            rows = node.arguments
        if rows:
            bindings[node.id] = {
                key: compile_binding(binding, nodes_by_id=nodes_by_id).to_dict()
                for key, binding in rows
            }
        if isinstance(node, DecisionNode | FilterNode):
            conditions[node.id] = _compiled_condition(
                node.condition,
                nodes_by_id=nodes_by_id,
            )
    return bindings, conditions, {
        key: sorted(value) for key, value in parents.items() if value
    }


_RUNTIME = r'''

def _pb_debug(node_id, event, detail=""):
    suffix = (" " + str(detail)) if detail else ""
    phantom.debug("[PB:{}:{}] {}{}".format(_PB_IR_SHA256[:12], node_id, event, suffix))


def _pb_result_key(node_id):
    return "playbook_builder:{}:{}".format(_PB_IR_SHA256, node_id)


def _pb_save(node_id, value):
    phantom.save_block_result(key=_pb_result_key(node_id), value=value, auto=True)


def _pb_load(node_id):
    return phantom.get_block_result(key=_pb_result_key(node_id))


def _pb_walk(value, path):
    current = [value]
    for segment in path:
        next_values = []
        for item in current:
            if segment == "*":
                if isinstance(item, (list, tuple)):
                    next_values.extend(item)
                elif isinstance(item, dict):
                    next_values.extend(item.values())
                continue
            if isinstance(item, dict):
                if segment in item:
                    next_values.append(item[segment])
                continue
            if isinstance(item, (list, tuple)):
                for child in item:
                    if isinstance(child, dict) and segment in child:
                        next_values.append(child[segment])
        current = next_values
        if not current:
            return None
    if len(current) == 1:
        return current[0]
    return current


def _pb_collect(container, datapath):
    rows = phantom.collect2(
        container=container,
        datapath=[datapath],
        scope="all",
    ) or []
    values = []
    for row in rows:
        value = row[0] if isinstance(row, (list, tuple)) and row else row
        if value is not None:
            values.append(value)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


def _pb_resolve(binding, container):
    kind = binding["kind"]
    if kind == "literal":
        return binding.get("value")
    if kind == "datapath":
        return _pb_collect(container, binding["datapath"])
    if kind == "node_output":
        if binding.get("datapath"):
            collected = _pb_collect(container, binding["datapath"])
            if collected is not None:
                return collected
        return _pb_walk(
            _pb_load(binding["source_node"]),
            binding.get("path") or [],
        )
    raise ValueError("unsupported compiled binding kind: {}".format(kind))


def _pb_values(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _pb_exists(value):
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, dict, set)):
        return len(value) > 0
    return True


def _pb_pair(op, left, right):
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "contains":
        return right in left
    if op == "starts_with":
        return str(left).startswith(str(right))
    if op == "ends_with":
        return str(left).endswith(str(right))
    if op == "in":
        return left in right
    raise ValueError("unsupported condition operator: {}".format(op))


def _pb_compare(op, left, right):
    left_values = _pb_values(left)
    right_values = _pb_values(right)
    outcomes = []
    for left_value in left_values:
        for right_value in right_values:
            try:
                outcomes.append(_pb_pair(op, left_value, right_value))
            except (TypeError, ValueError):
                outcomes.append(False)
    if op == "ne":
        return all(outcomes)
    return any(outcomes)


def _pb_condition(spec, container):
    op = spec["op"]
    if op == "exists":
        return _pb_exists(_pb_resolve(spec["value"], container))
    if op == "not_exists":
        return not _pb_exists(_pb_resolve(spec["value"], container))
    if op == "all":
        return all(_pb_condition(child, container) for child in spec["conditions"])
    if op == "any":
        return any(_pb_condition(child, container) for child in spec["conditions"])
    if op == "not":
        return not _pb_condition(spec["condition"], container)
    return _pb_compare(
        op,
        _pb_resolve(spec["left"], container),
        _pb_resolve(spec["right"], container),
    )


def _pb_resolve_map(node_id, container):
    return {
        key: _pb_resolve(binding, container)
        for key, binding in _PB_BINDINGS.get(node_id, {}).items()
    }


def _pb_coalesce(arguments):
    for key in sorted(arguments):
        value = arguments[key]
        if _pb_exists(value):
            return value
    return None


def _pb_deduplicate_values(arguments):
    output = []
    for key in sorted(arguments):
        for value in _pb_values(arguments[key]):
            if value not in output:
                output.append(value)
    return output


def _pb_normalize_indicator(arguments):
    value = arguments.get("value")
    if value is None and arguments:
        value = arguments[sorted(arguments)[0]]
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if item is not None]
    return str(value).strip().lower() if value is not None else None


def _pb_parse_iso8601(arguments):
    value = arguments.get("value")
    if value is None and arguments:
        value = arguments[sorted(arguments)[0]]
    if not isinstance(value, str):
        raise ValueError("parse_iso8601 requires a string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).isoformat()


_PB_HELPERS = {
    "coalesce": _pb_coalesce,
    "deduplicate_values": _pb_deduplicate_values,
    "normalize_indicator": _pb_normalize_indicator,
    "parse_iso8601": _pb_parse_iso8601,
}


def _pb_format(node, container):
    values = _pb_resolve_map(node["id"], container)
    rendered = node["template"].format_map(values)
    _pb_save(node["id"], {node["output"]: rendered})
    _pb_dispatch(node["next"], container=container, source_node=node["id"])


def _pb_code(node, container):
    try:
        arguments = _pb_resolve_map(node["id"], container)
        result = _PB_HELPERS[node["helper"]](arguments)
        _pb_save(node["id"], {node["output"]: result})
    except (KeyError, TypeError, ValueError) as exc:
        _pb_debug(node["id"], "helper_failed", type(exc).__name__)
        _pb_dispatch(node["on_failure"], container=container, source_node=node["id"])
        return
    _pb_dispatch(node["on_success"], container=container, source_node=node["id"])


def _pb_join(node, container, source_node):
    state_key = "__join_{}".format(node["id"])
    state = _pb_load(state_key) or {"arrived": [], "continued": False}
    if source_node and source_node not in state["arrived"]:
        state["arrived"].append(source_node)
        state["arrived"].sort()
    parents = set(_PB_JOIN_PARENTS.get(node["id"], []))
    arrived = set(state["arrived"])
    ready = bool(arrived) if node["strategy"] == "any" else parents.issubset(arrived)
    if ready and not state["continued"]:
        state["continued"] = True
        _pb_save(state_key, state)
        _pb_dispatch(node["next"], container=container, source_node=node["id"])
        return
    _pb_save(state_key, state)
    _pb_debug(node["id"], "waiting", "{}/{}".format(len(arrived), len(parents)))


def _pb_prompt_response(results):
    keys = ("response", "responses", "answer", "message")
    queue = [results]
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key in keys:
                if key in item and not isinstance(item[key], (dict, list, tuple)):
                    return item[key]
            queue.extend(item.values())
        elif isinstance(item, (list, tuple)):
            queue.extend(item)
    return None


def _pb_execute_action(node, container):
    if node["asset"]["kind"] != "asset":
        _pb_debug(node["id"], "blocked", "asset_unbound")
        _pb_dispatch(node["on_failure"], container=container, source_node=node["id"])
        return
    try:
        parameters = [_pb_resolve_map(node["id"], container)]
        phantom.act(
            action=node["action"],
            parameters=parameters,
            assets=[node["asset"]["name"]],
            callback=_PB_CALLBACKS[node["id"]],
            name="pb_{}".format(node["id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        _pb_debug(node["id"], "action_start_failed", type(exc).__name__)
        _pb_dispatch(node["on_failure"], container=container, source_node=node["id"])


def _pb_execute_prompt(node, container):
    response_types = [{
        "prompt": node["message"],
        "options": {"type": "list", "choices": node["choices"]},
    }]
    try:
        phantom.prompt2(
            role="Automation",
            message=node["message"],
            respond_in_mins=30,
            response_types=response_types,
            callback=_PB_CALLBACKS[node["id"]],
            name="pb_{}".format(node["id"]),
            container=container,
            scope="all",
        )
    except (KeyError, TypeError, ValueError) as exc:
        _pb_debug(node["id"], "prompt_start_failed", type(exc).__name__)
        _pb_dispatch(node["on_failure"], container=container, source_node=node["id"])


def _pb_dispatch(node_id, container, source_node=None):
    node = _PB_NODE_MAP[node_id]
    _pb_debug(node_id, "enter", node["type"])
    node_type = node["type"]
    if node_type == "start":
        _pb_dispatch(node["next"], container=container, source_node=node_id)
    elif node_type == "action":
        _pb_execute_action(node, container)
    elif node_type == "decision":
        target = node["on_true"] if _pb_condition(_PB_CONDITIONS[node_id], container) else node["on_false"]
        _pb_dispatch(target, container=container, source_node=node_id)
    elif node_type == "filter":
        target = node["on_match"] if _pb_condition(_PB_CONDITIONS[node_id], container) else node["on_no_match"]
        _pb_dispatch(target, container=container, source_node=node_id)
    elif node_type == "format":
        _pb_format(node, container)
    elif node_type == "code":
        _pb_code(node, container)
    elif node_type == "join":
        _pb_join(node, container, source_node)
    elif node_type == "prompt":
        _pb_execute_prompt(node, container)
    elif node_type == "end":
        _pb_save(node_id, {"outcome": node["outcome"]})
        _pb_debug(node_id, "outcome", node["outcome"])
    else:
        raise ValueError("unsupported node type: {}".format(node_type))
'''


def _callback_source(node: ActionNode | PromptNode) -> str:
    if isinstance(node, ActionNode):
        body = f'''    _pb_save({node.id!r}, results or [])
    target = {node.on_success!r} if success else {node.on_failure!r}
    _pb_debug({node.id!r}, "callback", "success" if success else "failure")
    _pb_dispatch(target, container=container, source_node={node.id!r})
'''
    else:
        timeout = node.on_timeout or node.on_failure
        body = f'''    _pb_save({node.id!r}, {{{node.response_key!r}: _pb_prompt_response(results), "raw": results or []}})
    target = {node.on_success!r} if success else {timeout!r}
    _pb_debug({node.id!r}, "callback", "success" if success else "timeout")
    _pb_dispatch(target, container=container, source_node={node.id!r})
'''
    return f'''def _pb_callback_{node.id}(
    action=None,
    success=None,
    container=None,
    results=None,
    handle=None,
    filtered_artifacts=None,
    filtered_results=None,
    custom_function=None,
    **kwargs
):
{body}
'''


def render_python(
    ir: PlaybookIR,
    *,
    compiler_version: str,
    artifact_schema_version: str,
) -> str:
    """Return byte-stable generated playbook source."""
    canonical = ir.canonical_json()
    encoded_ir = base64.b64encode(canonical.encode("utf-8")).decode("ascii")
    bindings, conditions, parents = _runtime_contract(ir)
    document = ir.to_dict(canonical=True)
    nodes = document["nodes"]
    callback_nodes = sorted(
        (
            node
            for node in ir.nodes
            if isinstance(node, ActionNode | PromptNode)
        ),
        key=lambda node: node.id,
    )
    callbacks = "\n".join(_callback_source(node) for node in callback_nodes)
    callback_map = "{\n" + "".join(
        f"    {node.id!r}: _pb_callback_{node.id},\n"
        for node in sorted(callback_nodes, key=lambda item: item.id)
    ) + "}"
    generated_at = ir.metadata.generated_at or "unspecified"
    model = ir.metadata.model or "none"
    prompt_version = ir.metadata.prompt_version or "none"
    header = f'''# Generated by SOAR Playbook Builder deterministic compiler.
# COMPILER-VERSION: {compiler_version}
# ARTIFACT-SCHEMA: {artifact_schema_version}
# IR-SHA256: {ir.sha256()}
# CAPABILITY-INDEX: {ir.metadata.capability_index_version}
# MODEL: {model}
# PROMPT-VERSION: {prompt_version}
# GENERATED-AT: {generated_at}
# PLAYBOOK-BUILDER-IR-BASE64: {encoded_ir}
#
# Do not edit generated code. Change the IR and compile again.

import json
from datetime import datetime

import phantom.rules as phantom

_PB_IR_SHA256 = {ir.sha256()!r}
_PB_COMPILER_VERSION = {compiler_version!r}
_PB_IR = json.loads({_json(canonical)})
_PB_NODES = json.loads({_json(_json(nodes))})
_PB_NODE_MAP = {{node["id"]: node for node in _PB_NODES}}
_PB_BINDINGS = json.loads({_json(_json(bindings))})
_PB_CONDITIONS = json.loads({_json(_json(conditions))})
_PB_JOIN_PARENTS = json.loads({_json(_json(parents))})
'''
    footer = f'''
{callbacks}
_PB_CALLBACKS = {callback_map}


def on_start(container):
    _pb_debug({ir.entrypoint!r}, "playbook_start", _PB_COMPILER_VERSION)
    _pb_dispatch({ir.entrypoint!r}, container=container)
    return


def on_finish(container, summary):
    phantom.debug("[PB:{{}}] playbook_finish".format(_PB_IR_SHA256[:12]))
    return
'''
    return header + _RUNTIME.lstrip("\n") + "\n" + footer.lstrip("\n")
