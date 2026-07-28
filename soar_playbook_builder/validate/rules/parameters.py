"""Action parameter completeness, literal types, and contains compatibility."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from capability.schema import ActionParameter
from ir.schema import (
    ActionNode,
    DatapathBinding,
    LiteralBinding,
    NodeOutputBinding,
)

from .base import ValidationContext, normalize

_HASH_RE = re.compile(r"^[A-Fa-f0-9]{32,128}$")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


def _literal_type_matches(value: object, data_type: str) -> bool:
    expected = normalize(data_type)
    if not expected:
        return True
    if expected in {"string", "password", "text", "file"}:
        return isinstance(value, str)
    if expected in {"numeric", "number", "float", "double"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected in {"integer", "int"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in {"boolean", "bool"}:
        return isinstance(value, bool)
    if expected in {"list", "array"}:
        return isinstance(value, list)
    if expected in {"object", "dictionary", "dict", "json"}:
        return isinstance(value, dict)
    return True


def _literal_contains(value: object, contains: str, context: ValidationContext) -> bool:
    expected = normalize(contains)
    values = value if isinstance(value, list) else [value]
    if not values:
        return False
    for item in values:
        if expected == "ip":
            try:
                ipaddress.ip_address(str(item))
            except ValueError:
                return False
        elif expected == "hash" and not _HASH_RE.fullmatch(str(item)):
            return False
        elif expected == "domain" and not _DOMAIN_RE.fullmatch(str(item)):
            return False
        elif expected == "url":
            parsed = urlsplit(str(item))
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return False
        elif expected == "severity":
            if normalize(str(item)) not in {
                normalize(value) for value in context.index.severities
            }:
                return False
        elif expected in {"username", "string"}:
            if not isinstance(item, str) or not item.strip():
                return False
    return True


def _producer_contains(
    binding: object,
    context: ValidationContext,
) -> tuple[set[str], bool]:
    if isinstance(binding, DatapathBinding):
        if binding.scope == "artifact" and len(binding.path) >= 2:
            if binding.path[-2] == "cef":
                field_name = binding.path[-1]
                field = next(
                    (
                        row
                        for row in context.index.cef_fields
                        if row.name.casefold() == field_name.casefold()
                    ),
                    None,
                )
                if field is not None:
                    return {normalize(item) for item in field.contains}, True
        if binding.scope == "container" and binding.path[-1] == "severity":
            return {"severity"}, True
        return set(), False
    if isinstance(binding, NodeOutputBinding):
        return set(), False
    return set(), True


def _check_contains(
    *,
    parameter: ActionParameter,
    binding: object,
    node: ActionNode,
    context: ValidationContext,
) -> None:
    expected = {normalize(item) for item in parameter.contains}
    if not expected:
        return
    if isinstance(binding, LiteralBinding):
        value = binding.to_dict()["value"]
        if not any(_literal_contains(value, item, context) for item in expected):
            context.add_gap(
                gap_id="CONTAINS_MISMATCH",
                severity="blocker",
                node=node.id,
                summary=f"Literal does not match contains metadata for {parameter.name!r}",
                detail={
                    "app": node.app,
                    "action": node.action,
                    "parameter": parameter.name,
                    "expected_contains": sorted(expected),
                    "binding_kind": "literal",
                },
            )
        return
    actual, verified = _producer_contains(binding, context)
    if verified and actual and not (expected & actual):
        context.add_gap(
            gap_id="CONTAINS_MISMATCH",
            severity="blocker",
            node=node.id,
            summary=f"Producer and consumer contains types conflict for {parameter.name!r}",
            detail={
                "app": node.app,
                "action": node.action,
                "parameter": parameter.name,
                "expected_contains": sorted(expected),
                "actual_contains": sorted(actual),
                "binding_kind": getattr(binding, "kind", ""),
            },
        )
    elif not verified:
        context.add_gap(
            gap_id="CONTAINS_UNVERIFIED",
            severity="warning",
            node=node.id,
            summary=f"Contains compatibility is not available for {parameter.name!r}",
            detail={
                "app": node.app,
                "action": node.action,
                "parameter": parameter.name,
                "expected_contains": sorted(expected),
                "binding_kind": getattr(binding, "kind", ""),
            },
        )


class ParameterRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            action = context.resolved_actions.get(node.id)
            if action is None:
                continue
            declared = {
                normalize(parameter.name): parameter
                for parameter in action.parameters
            }
            bound = {
                normalize(name): (name, binding)
                for name, binding in node.parameters
            }
            for key, (raw_name, _) in bound.items():
                if key not in declared:
                    context.add_gap(
                        gap_id="PARAMETER_UNKNOWN",
                        severity="blocker",
                        node=node.id,
                        summary=f"Parameter {raw_name!r} is not declared by the action",
                        detail={
                            "app": node.app,
                            "action": node.action,
                            "parameter": raw_name,
                            "available_parameters": sorted(
                                parameter.name for parameter in action.parameters
                            ),
                        },
                    )
            for key, parameter in sorted(
                declared.items(),
                key=lambda item: item[0],
            ):
                row = bound.get(key)
                if row is None:
                    if parameter.required and parameter.default_value is None:
                        context.add_gap(
                            gap_id="PARAMETER_REQUIRED",
                            severity="blocker",
                            node=node.id,
                            summary=f"Required parameter {parameter.name!r} is not bound",
                            detail={
                                "app": node.app,
                                "action": node.action,
                                "parameter": parameter.name,
                                "data_type": parameter.data_type,
                                "contains": sorted(parameter.contains),
                            },
                        )
                    continue
                _, binding = row
                if isinstance(binding, LiteralBinding):
                    value = binding.to_dict()["value"]
                    if not _literal_type_matches(value, parameter.data_type):
                        context.add_gap(
                            gap_id="PARAMETER_TYPE_MISMATCH",
                            severity="blocker",
                            node=node.id,
                            summary=f"Literal type is invalid for {parameter.name!r}",
                            detail={
                                "app": node.app,
                                "action": node.action,
                                "parameter": parameter.name,
                                "expected_data_type": parameter.data_type,
                                "actual_type": type(value).__name__,
                            },
                        )
                _check_contains(
                    parameter=parameter,
                    binding=binding,
                    node=node,
                    context=context,
                )
