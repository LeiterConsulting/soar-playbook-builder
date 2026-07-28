"""Graph policies beyond the strict structural IR validator."""

from __future__ import annotations

from ir.schema import JoinNode

from .base import ValidationContext


class GraphPolicyRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if isinstance(node, JoinNode) and node.strategy == "all":
                context.add_gap(
                    gap_id="ALL_JOIN_UNREACHABLE",
                    severity="blocker",
                    node=node.id,
                    summary="IR 1.0 has no fork construct that can satisfy an all join",
                    detail={
                        "strategy": node.strategy,
                        "ir_schema_version": context.ir.schema_version,
                    },
                )
