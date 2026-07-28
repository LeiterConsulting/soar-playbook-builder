"""Referenced custom-list, playbook, and vocabulary object checks."""

from __future__ import annotations

from ir.schema import ActionNode, LiteralBinding

from .base import ValidationContext, normalize


def _literal_parameter(node: ActionNode, names: set[str]) -> str | None:
    for key, binding in node.parameters:
        if normalize(key) not in names or not isinstance(binding, LiteralBinding):
            continue
        value = binding.to_dict()["value"]
        if isinstance(value, str):
            return value
    return None


def _check_inventory(
    *,
    context: ValidationContext,
    node: ActionNode,
    object_type: str,
    name: str,
    inventory: list[str],
    evidence_status: str,
) -> None:
    if evidence_status != "verified":
        context.add_gap(
            gap_id="OBJECT_INVENTORY_UNAVAILABLE",
            severity="blocker",
            node=node.id,
            summary=f"{object_type} inventory is not verified",
            detail={
                "object_type": object_type,
                "name": name,
                "evidence_status": evidence_status,
                "app": node.app,
                "action": node.action,
            },
        )
    elif normalize(name) not in {normalize(item) for item in inventory}:
        context.add_gap(
            gap_id="REFERENCED_OBJECT_MISSING",
            severity="blocker",
            node=node.id,
            summary=f"Referenced {object_type} {name!r} does not exist",
            detail={
                "object_type": object_type,
                "name": name,
                "available": sorted(inventory),
                "app": node.app,
                "action": node.action,
            },
        )


class ReferencedObjectRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            action_name = normalize(node.action)
            if action_name in {"add list", "add listitem", "get list"}:
                name = _literal_parameter(node, {"list", "list name", "list_name"})
                if name:
                    _check_inventory(
                        context=context,
                        node=node,
                        object_type="custom_list",
                        name=name,
                        inventory=context.index.custom_lists,
                        evidence_status=context.index.custom_lists_status,
                    )
            if action_name in {"run playbook", "playbook"}:
                name = _literal_parameter(
                    node,
                    {"playbook", "playbook name", "playbook_name"},
                )
                if name:
                    _check_inventory(
                        context=context,
                        node=node,
                        object_type="playbook",
                        name=name,
                        inventory=context.index.playbooks,
                        evidence_status=context.index.playbooks_status,
                    )
            if action_name == "set severity":
                severity = _literal_parameter(node, {"severity"})
                if severity and normalize(severity) not in {
                    normalize(item) for item in context.index.severities
                }:
                    context.add_gap(
                        gap_id="REFERENCED_OBJECT_MISSING",
                        severity="blocker",
                        node=node.id,
                        summary=f"Severity {severity!r} is not in local vocabulary",
                        detail={
                            "object_type": "severity",
                            "name": severity,
                            "available": sorted(context.index.severities),
                            "app": node.app,
                            "action": node.action,
                        },
                    )
