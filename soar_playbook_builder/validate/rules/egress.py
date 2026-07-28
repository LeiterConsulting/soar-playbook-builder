"""Operating-mode-aware egress classification and offline substitutions."""

from __future__ import annotations

from capability.index import load_egress_substitutions
from ir.schema import ActionNode
from validate.report import Substitution

from .base import ValidationContext, normalize


class EgressRule:
    def run(self, context: ValidationContext) -> None:
        substitutions = load_egress_substitutions()
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            action = context.resolved_actions.get(node.id)
            app = context.resolved_apps.get(node.id)
            if action is None or app is None:
                continue
            tag = action.requires_egress
            mode = context.ir.metadata.operating_mode
            if tag == "true" and mode in ("air_gapped", "restricted"):
                context.add_gap(
                    gap_id="EGRESS_REQUIRED",
                    severity="blocker",
                    node=node.id,
                    summary=(
                        f"Action {app.name}:{action.name} requires egress in "
                        f"{mode} mode"
                    ),
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "operating_mode": mode,
                        "requires_egress": tag,
                    },
                )
                lookup = f"{normalize(app.name).replace(' ', '_')}:{normalize(action.name)}"
                replacement = substitutions.get(lookup)
                if replacement:
                    target = replacement.get("offline_equivalent") or {}
                    context.substitutions.append(
                        Substitution(
                            node=node.id,
                            source_app=app.name,
                            source_action=action.name,
                            replacement_app=str(target.get("app") or ""),
                            replacement_action=str(target.get("action") or ""),
                            reason=str(replacement.get("note") or ""),
                            automatic=False,
                        )
                    )
            elif tag == "unknown":
                context.add_gap(
                    gap_id="EGRESS_UNKNOWN",
                    severity="blocker" if mode == "air_gapped" else "warning",
                    node=node.id,
                    summary=(
                        f"Network behavior is unknown for {app.name}:{action.name}"
                    ),
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "operating_mode": mode,
                        "requires_egress": tag,
                    },
                )
