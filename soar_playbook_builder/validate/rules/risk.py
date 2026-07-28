"""Require a provable upstream human prompt for known destructive actions."""

from __future__ import annotations

from ir.schema import ActionNode, PromptNode, node_edges

from .base import ValidationContext, normalize

_DESTRUCTIVE_ACTIONS = frozenset(
    {
        ("active directory", "disable account"),
        ("active_directory", "disable account"),
        ("clearpass cppm", "quarantine device"),
        ("clearpass_cppm", "quarantine device"),
        ("okta", "clear user sessions"),
        ("okta", "disable user"),
        ("panw", "block ip"),
    }
)


def _ancestors(context: ValidationContext, node_id: str) -> set[str]:
    reverse: dict[str, set[str]] = {node.id: set() for node in context.ir.nodes}
    for node in context.ir.nodes:
        for target in node_edges(node):
            reverse[target].add(node.id)
    seen: set[str] = set()
    stack = list(reverse[node_id])
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(reverse[current])
    return seen


class DestructiveActionRule:
    def run(self, context: ValidationContext) -> None:
        by_id = {node.id: node for node in context.ir.nodes}
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            identity = (normalize(node.app), normalize(node.action))
            if identity not in _DESTRUCTIVE_ACTIONS:
                continue
            ancestor_nodes = [
                by_id[node_id] for node_id in _ancestors(context, node.id)
            ]
            if not any(
                isinstance(ancestor, PromptNode) for ancestor in ancestor_nodes
            ):
                context.add_gap(
                    gap_id="DESTRUCTIVE_ACTION_REVIEW_REQUIRED",
                    severity="blocker",
                    node=node.id,
                    summary="Known destructive action has no upstream human prompt",
                    detail={
                        "app": node.app,
                        "action": node.action,
                        "asset": node.asset.to_dict(),
                    },
                )
