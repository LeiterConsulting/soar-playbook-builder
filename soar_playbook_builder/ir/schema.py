"""Typed playbook IR, strict parser, graph checks, and JSON Schema emitter."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Literal

IR_SCHEMA_VERSION = "1.0.0"
IR_SCHEMA_ID = "urn:soar-playbook-builder:ir:1.0.0"
MAX_NODES = 256
MAX_BINDINGS = 64
MAX_JSON_DEPTH = 8
MAX_LITERAL_COLLECTION = 64
MAX_LITERAL_BYTES = 64 * 1024

NODE_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
DOCUMENT_ID_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_. -]{0,127}$"
KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$"
PATH_SEGMENT_PATTERN = r"^(?:[A-Za-z0-9_-]{1,128}|\*)$"

_NODE_ID_RE = re.compile(NODE_ID_PATTERN)
_DOCUMENT_ID_RE = re.compile(DOCUMENT_ID_PATTERN)
_NAME_RE = re.compile(NAME_PATTERN)
_KEY_RE = re.compile(KEY_PATTERN)
_PATH_SEGMENT_RE = re.compile(PATH_SEGMENT_PATTERN)

ALLOWED_CODE_HELPERS = (
    "coalesce",
    "deduplicate_values",
    "normalize_indicator",
    "parse_iso8601",
)

ComparisonOperator = Literal[
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "starts_with",
    "ends_with",
    "in",
]
UnaryOperator = Literal["exists", "not_exists"]
GroupOperator = Literal["all", "any"]
OperatingMode = Literal["air_gapped", "restricted", "connected"]

COMPARISON_OPERATORS = (
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "starts_with",
    "ends_with",
    "in",
)
UNARY_OPERATORS = ("exists", "not_exists")
GROUP_OPERATORS = ("all", "any")
OPERATING_MODES = ("air_gapped", "restricted", "connected")


@dataclass(frozen=True)
class IRIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


class IRValidationError(ValueError):
    """One or more deterministic IR validation failures."""

    def __init__(self, issues: IRIssue | list[IRIssue] | tuple[IRIssue, ...]):
        if isinstance(issues, IRIssue):
            normalized = (issues,)
        else:
            normalized = tuple(issues)
        self.issues = normalized
        summary = "; ".join(
            f"{issue.code} at {issue.path}: {issue.message}"
            for issue in normalized
        )
        super().__init__(summary or "IR validation failed")

    def payload(self) -> dict[str, Any]:
        return {
            "status": "invalid",
            "schema_version": IR_SCHEMA_VERSION,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _fail(code: str, path: str, message: str) -> None:
    raise IRValidationError(IRIssue(code, path, message))


@dataclass(frozen=True)
class FrozenJSONObject:
    """Immutable representation of an arbitrary JSON object literal."""

    items: tuple[tuple[str, Any], ...]


def _freeze_json(value: Any, path: str = "$", depth: int = 0) -> Any:
    if depth > MAX_JSON_DEPTH:
        _fail(
            "LITERAL_TOO_DEEP",
            path,
            f"JSON literal nesting exceeds {MAX_JSON_DEPTH}",
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("NON_FINITE_NUMBER", path, "JSON numbers must be finite")
        return value
    if isinstance(value, list | tuple):
        if len(value) > MAX_LITERAL_COLLECTION:
            _fail(
                "LITERAL_TOO_LARGE",
                path,
                f"JSON arrays may contain at most {MAX_LITERAL_COLLECTION} items",
            )
        return tuple(
            _freeze_json(item, f"{path}/{index}", depth + 1)
            for index, item in enumerate(value)
        )
    if isinstance(value, dict):
        if len(value) > MAX_LITERAL_COLLECTION:
            _fail(
                "LITERAL_TOO_LARGE",
                path,
                f"JSON objects may contain at most {MAX_LITERAL_COLLECTION} keys",
            )
        frozen: list[tuple[str, Any]] = []
        for key in sorted(value):
            if not isinstance(key, str):
                _fail("INVALID_LITERAL_KEY", path, "JSON object keys must be strings")
            frozen.append(
                (key, _freeze_json(value[key], f"{path}/{key}", depth + 1))
            )
        return FrozenJSONObject(tuple(frozen))
    _fail(
        "INVALID_LITERAL_TYPE",
        path,
        f"{type(value).__name__} is not a JSON value",
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, FrozenJSONObject):
        return {key: _thaw_json(item) for key, item in value.items}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class LiteralBinding:
    value: Any
    kind: Literal["literal"] = "literal"

    def __post_init__(self) -> None:
        frozen = _freeze_json(self.value, "$/value")
        raw = json.dumps(
            _thaw_json(frozen),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(raw) > MAX_LITERAL_BYTES:
            _fail(
                "LITERAL_TOO_LARGE",
                "$/value",
                f"serialized literal exceeds {MAX_LITERAL_BYTES} bytes",
            )
        object.__setattr__(self, "value", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": _thaw_json(self.value)}


@dataclass(frozen=True)
class DatapathBinding:
    scope: Literal["artifact", "container", "playbook_input"]
    path: tuple[str, ...]
    kind: Literal["datapath"] = "datapath"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "scope": self.scope,
            "path": list(self.path),
        }


@dataclass(frozen=True)
class NodeOutputBinding:
    source_node: str
    path: tuple[str, ...]
    kind: Literal["node_output"] = "node_output"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source_node": self.source_node,
            "path": list(self.path),
        }


Binding = LiteralBinding | DatapathBinding | NodeOutputBinding
BindingItems = tuple[tuple[str, Binding], ...]


@dataclass(frozen=True)
class BoundAsset:
    name: str
    kind: Literal["asset"] = "asset"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "name": self.name}


@dataclass(frozen=True)
class UnboundAsset:
    kind: Literal["asset_unbound"] = "asset_unbound"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind}


AssetBinding = BoundAsset | UnboundAsset


@dataclass(frozen=True)
class ComparisonCondition:
    op: ComparisonOperator
    left: Binding
    right: Binding

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class UnaryCondition:
    op: UnaryOperator
    value: Binding

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.op, "value": self.value.to_dict()}


@dataclass(frozen=True)
class GroupCondition:
    op: GroupOperator
    conditions: tuple[Condition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "conditions": [condition.to_dict() for condition in self.conditions],
        }


@dataclass(frozen=True)
class NotCondition:
    condition: Condition
    op: Literal["not"] = "not"

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.op, "condition": self.condition.to_dict()}


Condition = ComparisonCondition | UnaryCondition | GroupCondition | NotCondition


@dataclass(frozen=True)
class IRMetadata:
    capability_index_version: str
    operating_mode: OperatingMode
    template_id: str = ""
    model: str = ""
    prompt_version: str = ""
    generated_at: str = ""
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "capability_index_version": self.capability_index_version,
            "operating_mode": self.operating_mode,
        }
        if self.template_id:
            payload["template_id"] = self.template_id
        if self.model:
            payload["model"] = self.model
        if self.prompt_version:
            payload["prompt_version"] = self.prompt_version
        if self.generated_at:
            payload["generated_at"] = self.generated_at
        if self.labels:
            payload["labels"] = list(self.labels)
        return payload


@dataclass(frozen=True)
class StartNode:
    id: str
    next: str
    label: str = ""
    type: Literal["start"] = "start"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(self, {"next": self.next})


@dataclass(frozen=True)
class ActionNode:
    id: str
    app: str
    action: str
    asset: AssetBinding
    parameters: BindingItems
    on_success: str
    on_failure: str
    label: str = ""
    type: Literal["action"] = "action"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {
                "app": self.app,
                "action": self.action,
                "asset": self.asset.to_dict(),
                "parameters": {
                    key: binding.to_dict() for key, binding in self.parameters
                },
                "on_success": self.on_success,
                "on_failure": self.on_failure,
            },
        )


@dataclass(frozen=True)
class DecisionNode:
    id: str
    condition: Condition
    on_true: str
    on_false: str
    label: str = ""
    type: Literal["decision"] = "decision"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {
                "condition": self.condition.to_dict(),
                "on_true": self.on_true,
                "on_false": self.on_false,
            },
        )


@dataclass(frozen=True)
class FilterNode:
    id: str
    condition: Condition
    on_match: str
    on_no_match: str
    label: str = ""
    type: Literal["filter"] = "filter"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {
                "condition": self.condition.to_dict(),
                "on_match": self.on_match,
                "on_no_match": self.on_no_match,
            },
        )


@dataclass(frozen=True)
class FormatNode:
    id: str
    template: str
    inputs: BindingItems
    output: str
    next: str
    label: str = ""
    type: Literal["format"] = "format"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {
                "template": self.template,
                "inputs": {
                    key: binding.to_dict() for key, binding in self.inputs
                },
                "output": self.output,
                "next": self.next,
            },
        )


@dataclass(frozen=True)
class PromptNode:
    id: str
    message: str
    response_key: str
    choices: tuple[str, ...]
    on_success: str
    on_failure: str
    on_timeout: str = ""
    label: str = ""
    type: Literal["prompt"] = "prompt"

    def to_dict(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "message": self.message,
            "response_key": self.response_key,
            "choices": list(self.choices),
            "on_success": self.on_success,
            "on_failure": self.on_failure,
        }
        if self.on_timeout:
            fields["on_timeout"] = self.on_timeout
        return _node_payload(self, fields)


@dataclass(frozen=True)
class CodeNode:
    id: str
    helper: str
    arguments: BindingItems
    output: str
    on_success: str
    on_failure: str
    label: str = ""
    type: Literal["code"] = "code"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {
                "helper": self.helper,
                "arguments": {
                    key: binding.to_dict() for key, binding in self.arguments
                },
                "output": self.output,
                "on_success": self.on_success,
                "on_failure": self.on_failure,
            },
        )


@dataclass(frozen=True)
class JoinNode:
    id: str
    strategy: Literal["all", "any"]
    next: str
    label: str = ""
    type: Literal["join"] = "join"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(
            self,
            {"strategy": self.strategy, "next": self.next},
        )


@dataclass(frozen=True)
class EndNode:
    id: str
    outcome: Literal["success", "failure", "neutral"]
    label: str = ""
    type: Literal["end"] = "end"

    def to_dict(self) -> dict[str, Any]:
        return _node_payload(self, {"outcome": self.outcome})


Node = (
    StartNode
    | ActionNode
    | DecisionNode
    | FilterNode
    | FormatNode
    | PromptNode
    | CodeNode
    | JoinNode
    | EndNode
)


def _node_payload(node: Node, fields: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": node.id, "type": node.type, **fields}
    if node.label:
        payload["label"] = node.label
    return payload


def _check_object(
    value: Any,
    *,
    path: str,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("OBJECT_REQUIRED", path, "value must be an object")
    allowed = set(required) | set(optional)
    unknown = sorted(set(value) - allowed)
    if unknown:
        _fail(
            "UNKNOWN_FIELD",
            f"{path}/{unknown[0]}",
            f"field {unknown[0]!r} is not allowed",
        )
    missing = [key for key in required if key not in value]
    if missing:
        _fail(
            "REQUIRED_FIELD_MISSING",
            f"{path}/{missing[0]}",
            f"field {missing[0]!r} is required",
        )
    return value


def _string(
    value: Any,
    *,
    path: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        _fail("STRING_REQUIRED", path, "value must be a string")
    if not allow_empty and not value:
        _fail("STRING_EMPTY", path, "value must not be empty")
    if len(value) > maximum:
        _fail("STRING_TOO_LONG", path, f"value exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        _fail("CONTROL_CHARACTER", path, "value contains a control character")
    if pattern is not None and not pattern.fullmatch(value):
        _fail("STRING_PATTERN", path, "value does not match the required format")
    return value


def _node_id(value: Any, path: str) -> str:
    return _string(value, path=path, maximum=64, pattern=_NODE_ID_RE)


def _name(value: Any, path: str) -> str:
    return _string(value, path=path, maximum=128, pattern=_NAME_RE)


def _key(value: Any, path: str) -> str:
    return _string(value, path=path, maximum=128, pattern=_KEY_RE)


def _path(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        _fail("PATH_REQUIRED", path, "path must be a non-empty array")
    if len(value) > 16:
        _fail("PATH_TOO_LONG", path, "path may contain at most 16 segments")
    return tuple(
        _string(
            segment,
            path=f"{path}/{index}",
            maximum=128,
            pattern=_PATH_SEGMENT_RE,
        )
        for index, segment in enumerate(value)
    )


def _parse_binding(value: Any, path: str) -> Binding:
    if not isinstance(value, dict):
        _fail("BINDING_REQUIRED", path, "binding must be an object")
    kind = value.get("kind")
    if kind == "literal":
        row = _check_object(value, path=path, required=("kind", "value"))
        return LiteralBinding(row["value"])
    if kind == "datapath":
        row = _check_object(
            value,
            path=path,
            required=("kind", "scope", "path"),
        )
        scope = row["scope"]
        if scope not in ("artifact", "container", "playbook_input"):
            _fail("INVALID_DATAPATH_SCOPE", f"{path}/scope", "scope is not supported")
        return DatapathBinding(scope=scope, path=_path(row["path"], f"{path}/path"))
    if kind == "node_output":
        row = _check_object(
            value,
            path=path,
            required=("kind", "source_node", "path"),
        )
        return NodeOutputBinding(
            source_node=_node_id(row["source_node"], f"{path}/source_node"),
            path=_path(row["path"], f"{path}/path"),
        )
    _fail(
        "UNKNOWN_BINDING_KIND",
        f"{path}/kind",
        "kind must be literal, datapath, or node_output",
    )


def _parse_binding_map(value: Any, path: str) -> BindingItems:
    if not isinstance(value, dict):
        _fail("BINDING_MAP_REQUIRED", path, "value must be an object")
    if len(value) > MAX_BINDINGS:
        _fail(
            "TOO_MANY_BINDINGS",
            path,
            f"binding map may contain at most {MAX_BINDINGS} entries",
        )
    parsed: list[tuple[str, Binding]] = []
    for raw_key in sorted(value):
        key = _key(raw_key, f"{path}/{raw_key}")
        parsed.append((key, _parse_binding(value[raw_key], f"{path}/{key}")))
    return tuple(parsed)


def _parse_asset(value: Any, path: str) -> AssetBinding:
    if not isinstance(value, dict):
        _fail("ASSET_BINDING_REQUIRED", path, "asset must be an object")
    kind = value.get("kind")
    if kind == "asset":
        row = _check_object(value, path=path, required=("kind", "name"))
        return BoundAsset(_name(row["name"], f"{path}/name"))
    if kind == "asset_unbound":
        _check_object(value, path=path, required=("kind",))
        return UnboundAsset()
    _fail(
        "UNKNOWN_ASSET_BINDING",
        f"{path}/kind",
        "kind must be asset or asset_unbound",
    )


def _parse_condition(value: Any, path: str, depth: int = 0) -> Condition:
    if depth > 16:
        _fail("CONDITION_TOO_DEEP", path, "condition nesting exceeds 16")
    if not isinstance(value, dict):
        _fail("CONDITION_REQUIRED", path, "condition must be an object")
    op = value.get("op")
    if op in COMPARISON_OPERATORS:
        row = _check_object(
            value,
            path=path,
            required=("op", "left", "right"),
        )
        return ComparisonCondition(
            op=op,
            left=_parse_binding(row["left"], f"{path}/left"),
            right=_parse_binding(row["right"], f"{path}/right"),
        )
    if op in UNARY_OPERATORS:
        row = _check_object(value, path=path, required=("op", "value"))
        return UnaryCondition(
            op=op,
            value=_parse_binding(row["value"], f"{path}/value"),
        )
    if op in GROUP_OPERATORS:
        row = _check_object(value, path=path, required=("op", "conditions"))
        raw_conditions = row["conditions"]
        if not isinstance(raw_conditions, list) or not raw_conditions:
            _fail(
                "CONDITIONS_REQUIRED",
                f"{path}/conditions",
                "conditions must be a non-empty array",
            )
        if len(raw_conditions) > 16:
            _fail(
                "TOO_MANY_CONDITIONS",
                f"{path}/conditions",
                "condition group may contain at most 16 entries",
            )
        return GroupCondition(
            op=op,
            conditions=tuple(
                _parse_condition(item, f"{path}/conditions/{index}", depth + 1)
                for index, item in enumerate(raw_conditions)
            ),
        )
    if op == "not":
        row = _check_object(value, path=path, required=("op", "condition"))
        return NotCondition(
            condition=_parse_condition(
                row["condition"],
                f"{path}/condition",
                depth + 1,
            )
        )
    _fail(
        "UNKNOWN_CONDITION_OPERATOR",
        f"{path}/op",
        "condition operator is not supported",
    )


def _optional_label(row: dict[str, Any], path: str) -> str:
    if "label" not in row:
        return ""
    return _string(
        row["label"],
        path=f"{path}/label",
        maximum=256,
        allow_empty=True,
    )


def _parse_node(value: Any, path: str) -> Node:
    if not isinstance(value, dict):
        _fail("NODE_REQUIRED", path, "node must be an object")
    node_type = value.get("type")
    common_optional = ("label",)
    if node_type == "start":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "next"),
            optional=common_optional,
        )
        return StartNode(
            id=_node_id(row["id"], f"{path}/id"),
            next=_node_id(row["next"], f"{path}/next"),
            label=_optional_label(row, path),
        )
    if node_type == "action":
        row = _check_object(
            value,
            path=path,
            required=(
                "id",
                "type",
                "app",
                "action",
                "asset",
                "parameters",
                "on_success",
                "on_failure",
            ),
            optional=common_optional,
        )
        return ActionNode(
            id=_node_id(row["id"], f"{path}/id"),
            app=_name(row["app"], f"{path}/app"),
            action=_name(row["action"], f"{path}/action"),
            asset=_parse_asset(row["asset"], f"{path}/asset"),
            parameters=_parse_binding_map(row["parameters"], f"{path}/parameters"),
            on_success=_node_id(row["on_success"], f"{path}/on_success"),
            on_failure=_node_id(row["on_failure"], f"{path}/on_failure"),
            label=_optional_label(row, path),
        )
    if node_type == "decision":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "condition", "on_true", "on_false"),
            optional=common_optional,
        )
        return DecisionNode(
            id=_node_id(row["id"], f"{path}/id"),
            condition=_parse_condition(row["condition"], f"{path}/condition"),
            on_true=_node_id(row["on_true"], f"{path}/on_true"),
            on_false=_node_id(row["on_false"], f"{path}/on_false"),
            label=_optional_label(row, path),
        )
    if node_type == "filter":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "condition", "on_match", "on_no_match"),
            optional=common_optional,
        )
        return FilterNode(
            id=_node_id(row["id"], f"{path}/id"),
            condition=_parse_condition(row["condition"], f"{path}/condition"),
            on_match=_node_id(row["on_match"], f"{path}/on_match"),
            on_no_match=_node_id(row["on_no_match"], f"{path}/on_no_match"),
            label=_optional_label(row, path),
        )
    if node_type == "format":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "template", "inputs", "output", "next"),
            optional=common_optional,
        )
        return FormatNode(
            id=_node_id(row["id"], f"{path}/id"),
            template=_string(
                row["template"],
                path=f"{path}/template",
                maximum=4096,
            ),
            inputs=_parse_binding_map(row["inputs"], f"{path}/inputs"),
            output=_key(row["output"], f"{path}/output"),
            next=_node_id(row["next"], f"{path}/next"),
            label=_optional_label(row, path),
        )
    if node_type == "prompt":
        row = _check_object(
            value,
            path=path,
            required=(
                "id",
                "type",
                "message",
                "response_key",
                "choices",
                "on_success",
                "on_failure",
            ),
            optional=("on_timeout", "label"),
        )
        raw_choices = row["choices"]
        if not isinstance(raw_choices, list) or not 1 <= len(raw_choices) <= 16:
            _fail(
                "INVALID_PROMPT_CHOICES",
                f"{path}/choices",
                "choices must contain between 1 and 16 strings",
            )
        choices = tuple(
            _string(
                choice,
                path=f"{path}/choices/{index}",
                maximum=256,
            )
            for index, choice in enumerate(raw_choices)
        )
        if len(set(choices)) != len(choices):
            _fail(
                "DUPLICATE_PROMPT_CHOICE",
                f"{path}/choices",
                "prompt choices must be unique",
            )
        return PromptNode(
            id=_node_id(row["id"], f"{path}/id"),
            message=_string(
                row["message"],
                path=f"{path}/message",
                maximum=4096,
            ),
            response_key=_key(row["response_key"], f"{path}/response_key"),
            choices=choices,
            on_success=_node_id(row["on_success"], f"{path}/on_success"),
            on_failure=_node_id(row["on_failure"], f"{path}/on_failure"),
            on_timeout=(
                _node_id(row["on_timeout"], f"{path}/on_timeout")
                if row.get("on_timeout")
                else ""
            ),
            label=_optional_label(row, path),
        )
    if node_type == "code":
        row = _check_object(
            value,
            path=path,
            required=(
                "id",
                "type",
                "helper",
                "arguments",
                "output",
                "on_success",
                "on_failure",
            ),
            optional=common_optional,
        )
        helper = _string(
            row["helper"],
            path=f"{path}/helper",
            maximum=64,
            pattern=_KEY_RE,
        )
        if helper not in ALLOWED_CODE_HELPERS:
            _fail(
                "HELPER_NOT_ALLOWED",
                f"{path}/helper",
                f"helper must be one of {', '.join(ALLOWED_CODE_HELPERS)}",
            )
        return CodeNode(
            id=_node_id(row["id"], f"{path}/id"),
            helper=helper,
            arguments=_parse_binding_map(row["arguments"], f"{path}/arguments"),
            output=_key(row["output"], f"{path}/output"),
            on_success=_node_id(row["on_success"], f"{path}/on_success"),
            on_failure=_node_id(row["on_failure"], f"{path}/on_failure"),
            label=_optional_label(row, path),
        )
    if node_type == "join":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "strategy", "next"),
            optional=common_optional,
        )
        strategy = row["strategy"]
        if strategy not in ("all", "any"):
            _fail("INVALID_JOIN_STRATEGY", f"{path}/strategy", "strategy is invalid")
        return JoinNode(
            id=_node_id(row["id"], f"{path}/id"),
            strategy=strategy,
            next=_node_id(row["next"], f"{path}/next"),
            label=_optional_label(row, path),
        )
    if node_type == "end":
        row = _check_object(
            value,
            path=path,
            required=("id", "type", "outcome"),
            optional=common_optional,
        )
        outcome = row["outcome"]
        if outcome not in ("success", "failure", "neutral"):
            _fail("INVALID_END_OUTCOME", f"{path}/outcome", "outcome is invalid")
        return EndNode(
            id=_node_id(row["id"], f"{path}/id"),
            outcome=outcome,
            label=_optional_label(row, path),
        )
    _fail(
        "UNKNOWN_NODE_TYPE",
        f"{path}/type",
        "node type is not supported",
    )


def _parse_metadata(value: Any, path: str) -> IRMetadata:
    row = _check_object(
        value,
        path=path,
        required=("capability_index_version", "operating_mode"),
        optional=(
            "template_id",
            "model",
            "prompt_version",
            "generated_at",
            "labels",
        ),
    )
    mode = row["operating_mode"]
    if mode not in OPERATING_MODES:
        _fail(
            "INVALID_OPERATING_MODE",
            f"{path}/operating_mode",
            "operating mode is not supported",
        )
    labels_raw = row.get("labels") or []
    if not isinstance(labels_raw, list) or len(labels_raw) > 32:
        _fail(
            "INVALID_METADATA_LABELS",
            f"{path}/labels",
            "labels must be an array of at most 32 strings",
        )
    labels = tuple(
        _string(
            label,
            path=f"{path}/labels/{index}",
            maximum=128,
            pattern=_KEY_RE,
        )
        for index, label in enumerate(labels_raw)
    )
    if len(set(labels)) != len(labels):
        _fail(
            "DUPLICATE_METADATA_LABEL",
            f"{path}/labels",
            "metadata labels must be unique",
        )
    return IRMetadata(
        capability_index_version=_string(
            row["capability_index_version"],
            path=f"{path}/capability_index_version",
            maximum=128,
        ),
        operating_mode=mode,
        template_id=_string(
            row.get("template_id") or "",
            path=f"{path}/template_id",
            maximum=128,
            allow_empty=True,
        ),
        model=_string(
            row.get("model") or "",
            path=f"{path}/model",
            maximum=256,
            allow_empty=True,
        ),
        prompt_version=_string(
            row.get("prompt_version") or "",
            path=f"{path}/prompt_version",
            maximum=128,
            allow_empty=True,
        ),
        generated_at=_string(
            row.get("generated_at") or "",
            path=f"{path}/generated_at",
            maximum=64,
            allow_empty=True,
        ),
        labels=labels,
    )


def migrate_ir_document(
    document: dict[str, Any],
    *,
    target_version: str = IR_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return a detached document at the requested schema version.

    Version 1.0.0 is the first published IR, so no legacy transformation is
    intentionally guessed. Future migrations must be explicit functions.
    """
    if not isinstance(document, dict):
        _fail("OBJECT_REQUIRED", "$", "IR document must be an object")
    version = document.get("schema_version")
    if not isinstance(version, str) or not version:
        _fail(
            "SCHEMA_VERSION_REQUIRED",
            "$/schema_version",
            "schema_version is required",
        )
    if target_version != IR_SCHEMA_VERSION:
        _fail(
            "UNSUPPORTED_TARGET_VERSION",
            "$/schema_version",
            f"target version {target_version!r} is not supported",
        )
    if version != target_version:
        _fail(
            "UNSUPPORTED_SCHEMA_VERSION",
            "$/schema_version",
            f"schema version {version!r} is not supported",
        )

    def reject_non_finite(value: Any, path: str) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            _fail("NON_FINITE_NUMBER", path, "JSON numbers must be finite")
        if isinstance(value, list | tuple):
            for index, item in enumerate(value):
                reject_non_finite(item, f"{path}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                reject_non_finite(item, f"{path}/{key}")

    reject_non_finite(document, "$")
    try:
        return json.loads(json.dumps(document, allow_nan=False))
    except (TypeError, ValueError) as exc:
        _fail("NOT_JSON_SERIALIZABLE", "$", str(exc))


@dataclass(frozen=True)
class PlaybookIR:
    id: str
    name: str
    description: str
    entrypoint: str
    nodes: tuple[Node, ...]
    metadata: IRMetadata
    schema_version: Literal["1.0.0"] = IR_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> PlaybookIR:
        row = _check_object(
            migrate_ir_document(document),
            path="$",
            required=(
                "schema_version",
                "id",
                "name",
                "description",
                "entrypoint",
                "nodes",
                "metadata",
            ),
        )
        raw_nodes = row["nodes"]
        if not isinstance(raw_nodes, list) or not raw_nodes:
            _fail("NODES_REQUIRED", "$/nodes", "nodes must be a non-empty array")
        if len(raw_nodes) > MAX_NODES:
            _fail(
                "TOO_MANY_NODES",
                "$/nodes",
                f"IR may contain at most {MAX_NODES} nodes",
            )
        ir = cls(
            id=_string(
                row["id"],
                path="$/id",
                maximum=64,
                pattern=_DOCUMENT_ID_RE,
            ),
            name=_string(row["name"], path="$/name", maximum=256),
            description=_string(
                row["description"],
                path="$/description",
                maximum=4096,
                allow_empty=True,
            ),
            entrypoint=_node_id(row["entrypoint"], "$/entrypoint"),
            nodes=tuple(
                _parse_node(node, f"$/nodes/{index}")
                for index, node in enumerate(raw_nodes)
            ),
            metadata=_parse_metadata(row["metadata"], "$/metadata"),
        )
        validate_graph(ir)
        return ir

    def to_dict(self, *, canonical: bool = False) -> dict[str, Any]:
        nodes = self.nodes
        if canonical:
            nodes = tuple(sorted(nodes, key=lambda node: node.id))
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "nodes": [node.to_dict() for node in nodes],
            "metadata": self.metadata.to_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(canonical=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def node_edges(node: Node) -> tuple[str, ...]:
    if isinstance(node, StartNode | FormatNode | JoinNode):
        return (node.next,)
    if isinstance(node, ActionNode | CodeNode):
        return (node.on_success, node.on_failure)
    if isinstance(node, DecisionNode):
        return (node.on_true, node.on_false)
    if isinstance(node, FilterNode):
        return (node.on_match, node.on_no_match)
    if isinstance(node, PromptNode):
        edges = [node.on_success, node.on_failure]
        if node.on_timeout:
            edges.append(node.on_timeout)
        return tuple(edges)
    return ()


def _condition_bindings(condition: Condition) -> tuple[Binding, ...]:
    if isinstance(condition, ComparisonCondition):
        return (condition.left, condition.right)
    if isinstance(condition, UnaryCondition):
        return (condition.value,)
    if isinstance(condition, GroupCondition):
        return tuple(
            binding
            for child in condition.conditions
            for binding in _condition_bindings(child)
        )
    return _condition_bindings(condition.condition)


def node_bindings(node: Node) -> tuple[Binding, ...]:
    if isinstance(node, ActionNode):
        return tuple(binding for _, binding in node.parameters)
    if isinstance(node, FormatNode):
        return tuple(binding for _, binding in node.inputs)
    if isinstance(node, CodeNode):
        return tuple(binding for _, binding in node.arguments)
    if isinstance(node, DecisionNode | FilterNode):
        return _condition_bindings(node.condition)
    return ()


def _reachable_from(start: str, adjacency: dict[str, tuple[str, ...]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, ()))
    return seen


def _has_cycle(
    node_id: str,
    adjacency: dict[str, tuple[str, ...]],
    visiting: set[str],
    visited: set[str],
) -> bool:
    if node_id in visiting:
        return True
    if node_id in visited:
        return False
    visiting.add(node_id)
    for target in adjacency.get(node_id, ()):
        if _has_cycle(target, adjacency, visiting, visited):
            return True
    visiting.remove(node_id)
    visited.add(node_id)
    return False


def _ancestors(
    node_id: str,
    reverse: dict[str, set[str]],
) -> set[str]:
    seen: set[str] = set()
    stack = list(reverse.get(node_id, set()))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(reverse.get(current, set()))
    return seen


def validate_graph(ir: PlaybookIR) -> None:
    """Validate topology and prior-node binding rules."""
    issues: list[IRIssue] = []
    by_id: dict[str, Node] = {}
    node_paths: dict[str, str] = {}
    for index, node in enumerate(ir.nodes):
        path = f"$/nodes/{index}"
        if node.id in by_id:
            issues.append(
                IRIssue("DUPLICATE_NODE_ID", f"{path}/id", f"duplicate id {node.id!r}")
            )
        else:
            by_id[node.id] = node
            node_paths[node.id] = path

    starts = [node for node in ir.nodes if isinstance(node, StartNode)]
    ends = [node for node in ir.nodes if isinstance(node, EndNode)]
    if len(starts) != 1:
        issues.append(
            IRIssue(
                "START_NODE_COUNT",
                "$/nodes",
                "graph must contain exactly one start node",
            )
        )
    if not ends:
        issues.append(
            IRIssue("END_NODE_REQUIRED", "$/nodes", "graph must contain an end node")
        )
    if ir.entrypoint not in by_id:
        issues.append(
            IRIssue(
                "ENTRYPOINT_MISSING",
                "$/entrypoint",
                f"entrypoint {ir.entrypoint!r} does not exist",
            )
        )
    elif not isinstance(by_id[ir.entrypoint], StartNode):
        issues.append(
            IRIssue(
                "ENTRYPOINT_NOT_START",
                "$/entrypoint",
                "entrypoint must reference the start node",
            )
        )

    adjacency: dict[str, tuple[str, ...]] = {}
    reverse: dict[str, set[str]] = {node_id: set() for node_id in by_id}
    for node in ir.nodes:
        edges = node_edges(node)
        adjacency[node.id] = edges
        for edge_index, target in enumerate(edges):
            if target not in by_id:
                issues.append(
                    IRIssue(
                        "DANGLING_EDGE",
                        f"{node_paths.get(node.id, '$/nodes')}/edges/{edge_index}",
                        f"target {target!r} does not exist",
                    )
                )
            else:
                reverse[target].add(node.id)

    if ir.entrypoint in by_id:
        reachable = _reachable_from(ir.entrypoint, adjacency)
        for node_id in sorted(set(by_id) - reachable):
            issues.append(
                IRIssue(
                    "UNREACHABLE_NODE",
                    f"{node_paths[node_id]}/id",
                    f"node {node_id!r} is unreachable",
                )
            )
        if _has_cycle(ir.entrypoint, adjacency, set(), set()):
            issues.append(
                IRIssue(
                    "GRAPH_CYCLE",
                    "$/nodes",
                    "graph must be acyclic; explicit loop nodes are not supported",
                )
            )

    for node_id, node in by_id.items():
        incoming = reverse.get(node_id, set())
        if isinstance(node, StartNode) and incoming:
            issues.append(
                IRIssue(
                    "START_HAS_INCOMING_EDGE",
                    f"{node_paths[node_id]}/id",
                    "start node may not have incoming edges",
                )
            )
        if isinstance(node, JoinNode) and len(incoming) < 2:
            issues.append(
                IRIssue(
                    "JOIN_REQUIRES_BRANCHES",
                    f"{node_paths[node_id]}/id",
                    "join node requires at least two distinct predecessors",
                )
            )
        if (
            len(incoming) > 1
            and not isinstance(node, JoinNode | EndNode)
        ):
            issues.append(
                IRIssue(
                    "BRANCHES_REQUIRE_JOIN",
                    f"{node_paths[node_id]}/id",
                    "multiple branches may merge only through a join or end node",
                )
            )

    output_types = (ActionNode, FormatNode, PromptNode, CodeNode)
    for node_id, node in by_id.items():
        ancestors = _ancestors(node_id, reverse)
        for binding_index, binding in enumerate(node_bindings(node)):
            if not isinstance(binding, NodeOutputBinding):
                continue
            source = by_id.get(binding.source_node)
            path = f"{node_paths[node_id]}/bindings/{binding_index}/source_node"
            if source is None:
                issues.append(
                    IRIssue(
                        "OUTPUT_SOURCE_MISSING",
                        path,
                        f"source node {binding.source_node!r} does not exist",
                    )
                )
            elif not isinstance(source, output_types):
                issues.append(
                    IRIssue(
                        "OUTPUT_SOURCE_INVALID",
                        path,
                        f"node {binding.source_node!r} does not produce bindable output",
                    )
                )
            elif binding.source_node not in ancestors:
                issues.append(
                    IRIssue(
                        "OUTPUT_SOURCE_NOT_PRIOR",
                        path,
                        f"node {binding.source_node!r} is not a prior node",
                    )
                )

    if issues:
        raise IRValidationError(issues)


def _closed_object(
    properties: dict[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _string_schema(
    *,
    maximum: int,
    minimum: int = 1,
    pattern: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "string",
        "minLength": minimum,
        "maxLength": maximum,
    }
    if pattern:
        payload["pattern"] = pattern
    return payload


def _binding_map_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "maxProperties": MAX_BINDINGS,
        "propertyNames": {"pattern": KEY_PATTERN},
        "additionalProperties": {"$ref": "#/$defs/binding"},
    }


def _node_schema(
    node_type: str,
    fields: dict[str, Any],
    required_fields: tuple[str, ...],
    *,
    optional_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    properties = {
        "id": _string_schema(maximum=64, pattern=NODE_ID_PATTERN),
        "type": {"const": node_type},
        **fields,
        **(optional_fields or {}),
        "label": _string_schema(maximum=256, minimum=0),
    }
    return _closed_object(
        properties,
        ("id", "type", *required_fields),
    )


def ir_json_schema() -> dict[str, Any]:
    """Generate strict draft-2020-12 schema from the IR source constants."""
    node_id = _string_schema(maximum=64, pattern=NODE_ID_PATTERN)
    name = _string_schema(maximum=128, pattern=NAME_PATTERN)
    key = _string_schema(maximum=128, pattern=KEY_PATTERN)
    path = {
        "type": "array",
        "minItems": 1,
        "maxItems": 16,
        "items": _string_schema(maximum=128, pattern=PATH_SEGMENT_PATTERN),
    }
    binding_map = _binding_map_schema()
    defs: dict[str, Any] = {
        "jsonScalar": {
            "oneOf": [
                {"type": "null"},
                {"type": "boolean"},
                {"type": "number"},
                {"type": "string"},
            ]
        },
        "jsonArray": {
            "type": "array",
            "maxItems": MAX_LITERAL_COLLECTION,
            "items": {"$ref": "#/$defs/jsonValue"},
        },
        "jsonObject": {
            "type": "object",
            "maxProperties": MAX_LITERAL_COLLECTION,
            "additionalProperties": {"$ref": "#/$defs/jsonValue"},
        },
        "jsonValue": {
            "oneOf": [
                {"$ref": "#/$defs/jsonScalar"},
                {"$ref": "#/$defs/jsonArray"},
                {"$ref": "#/$defs/jsonObject"},
            ]
        },
        "literalBinding": _closed_object(
            {
                "kind": {"const": "literal"},
                "value": {"$ref": "#/$defs/jsonValue"},
            },
            ("kind", "value"),
        ),
        "datapathBinding": _closed_object(
            {
                "kind": {"const": "datapath"},
                "scope": {
                    "enum": ["artifact", "container", "playbook_input"]
                },
                "path": path,
            },
            ("kind", "scope", "path"),
        ),
        "nodeOutputBinding": _closed_object(
            {
                "kind": {"const": "node_output"},
                "source_node": node_id,
                "path": path,
            },
            ("kind", "source_node", "path"),
        ),
        "binding": {
            "oneOf": [
                {"$ref": "#/$defs/literalBinding"},
                {"$ref": "#/$defs/datapathBinding"},
                {"$ref": "#/$defs/nodeOutputBinding"},
            ]
        },
        "boundAsset": _closed_object(
            {"kind": {"const": "asset"}, "name": name},
            ("kind", "name"),
        ),
        "unboundAsset": _closed_object(
            {"kind": {"const": "asset_unbound"}},
            ("kind",),
        ),
        "assetBinding": {
            "oneOf": [
                {"$ref": "#/$defs/boundAsset"},
                {"$ref": "#/$defs/unboundAsset"},
            ]
        },
        "comparisonCondition": _closed_object(
            {
                "op": {"enum": list(COMPARISON_OPERATORS)},
                "left": {"$ref": "#/$defs/binding"},
                "right": {"$ref": "#/$defs/binding"},
            },
            ("op", "left", "right"),
        ),
        "unaryCondition": _closed_object(
            {
                "op": {"enum": list(UNARY_OPERATORS)},
                "value": {"$ref": "#/$defs/binding"},
            },
            ("op", "value"),
        ),
        "groupCondition": _closed_object(
            {
                "op": {"enum": list(GROUP_OPERATORS)},
                "conditions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": {"$ref": "#/$defs/condition"},
                },
            },
            ("op", "conditions"),
        ),
        "notCondition": _closed_object(
            {
                "op": {"const": "not"},
                "condition": {"$ref": "#/$defs/condition"},
            },
            ("op", "condition"),
        ),
        "condition": {
            "oneOf": [
                {"$ref": "#/$defs/comparisonCondition"},
                {"$ref": "#/$defs/unaryCondition"},
                {"$ref": "#/$defs/groupCondition"},
                {"$ref": "#/$defs/notCondition"},
            ]
        },
        "metadata": _closed_object(
            {
                "capability_index_version": _string_schema(maximum=128),
                "operating_mode": {"enum": list(OPERATING_MODES)},
                "template_id": _string_schema(maximum=128, minimum=0),
                "model": _string_schema(maximum=256, minimum=0),
                "prompt_version": _string_schema(maximum=128, minimum=0),
                "generated_at": _string_schema(maximum=64, minimum=0),
                "labels": {
                    "type": "array",
                    "maxItems": 32,
                    "uniqueItems": True,
                    "items": key,
                },
            },
            ("capability_index_version", "operating_mode"),
        ),
    }
    defs.update(
        {
            "startNode": _node_schema(
                "start",
                {"next": node_id},
                ("next",),
            ),
            "actionNode": _node_schema(
                "action",
                {
                    "app": name,
                    "action": name,
                    "asset": {"$ref": "#/$defs/assetBinding"},
                    "parameters": binding_map,
                    "on_success": node_id,
                    "on_failure": node_id,
                },
                (
                    "app",
                    "action",
                    "asset",
                    "parameters",
                    "on_success",
                    "on_failure",
                ),
            ),
            "decisionNode": _node_schema(
                "decision",
                {
                    "condition": {"$ref": "#/$defs/condition"},
                    "on_true": node_id,
                    "on_false": node_id,
                },
                ("condition", "on_true", "on_false"),
            ),
            "filterNode": _node_schema(
                "filter",
                {
                    "condition": {"$ref": "#/$defs/condition"},
                    "on_match": node_id,
                    "on_no_match": node_id,
                },
                ("condition", "on_match", "on_no_match"),
            ),
            "formatNode": _node_schema(
                "format",
                {
                    "template": _string_schema(maximum=4096),
                    "inputs": binding_map,
                    "output": key,
                    "next": node_id,
                },
                ("template", "inputs", "output", "next"),
            ),
            "promptNode": _node_schema(
                "prompt",
                {
                    "message": _string_schema(maximum=4096),
                    "response_key": key,
                    "choices": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 16,
                        "uniqueItems": True,
                        "items": _string_schema(maximum=256),
                    },
                    "on_success": node_id,
                    "on_failure": node_id,
                },
                (
                    "message",
                    "response_key",
                    "choices",
                    "on_success",
                    "on_failure",
                ),
                optional_fields={"on_timeout": node_id},
            ),
            "codeNode": _node_schema(
                "code",
                {
                    "helper": {"enum": list(ALLOWED_CODE_HELPERS)},
                    "arguments": binding_map,
                    "output": key,
                    "on_success": node_id,
                    "on_failure": node_id,
                },
                (
                    "helper",
                    "arguments",
                    "output",
                    "on_success",
                    "on_failure",
                ),
            ),
            "joinNode": _node_schema(
                "join",
                {"strategy": {"enum": ["all", "any"]}, "next": node_id},
                ("strategy", "next"),
            ),
            "endNode": _node_schema(
                "end",
                {"outcome": {"enum": ["success", "failure", "neutral"]}},
                ("outcome",),
            ),
        }
    )
    defs["node"] = {
        "oneOf": [
            {"$ref": f"#/$defs/{name}"}
            for name in (
                "startNode",
                "actionNode",
                "decisionNode",
                "filterNode",
                "formatNode",
                "promptNode",
                "codeNode",
                "joinNode",
                "endNode",
            )
        ]
    }
    root = _closed_object(
        {
            "schema_version": {"const": IR_SCHEMA_VERSION},
            "id": _string_schema(maximum=64, pattern=DOCUMENT_ID_PATTERN),
            "name": _string_schema(maximum=256),
            "description": _string_schema(maximum=4096, minimum=0),
            "entrypoint": node_id,
            "nodes": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_NODES,
                "items": {"$ref": "#/$defs/node"},
            },
            "metadata": {"$ref": "#/$defs/metadata"},
        },
        (
            "schema_version",
            "id",
            "name",
            "description",
            "entrypoint",
            "nodes",
            "metadata",
        ),
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": IR_SCHEMA_ID,
        "title": "SOAR Playbook Builder IR",
        **root,
        "$defs": defs,
    }
