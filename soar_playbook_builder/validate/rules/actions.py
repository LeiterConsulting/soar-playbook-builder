"""Exact app/action resolution rules."""

from __future__ import annotations

from ir.schema import ActionNode

from .base import ValidationContext


class ActionResolutionRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            app = context.resolve_app(node.app)
            if app is None:
                context.add_gap(
                    gap_id="ACTION_APP_UNKNOWN",
                    severity="blocker",
                    node=node.id,
                    summary=f"App {node.app!r} is absent from the capability index",
                    detail={"app": node.app, "action": node.action},
                )
                continue
            context.resolved_apps[node.id] = app
            action = context.resolve_action(app, node.action)
            if action is None:
                context.add_gap(
                    gap_id="ACTION_NOT_FOUND",
                    severity="blocker",
                    node=node.id,
                    summary=f"Action {node.action!r} is not exposed by {app.name!r}",
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "available_actions": sorted(
                            item.name for item in app.actions
                        ),
                    },
                )
                continue
            context.resolved_actions[node.id] = action
            if app.source == "baseline":
                context.add_gap(
                    gap_id="APP_INSTALLATION_UNVERIFIED",
                    severity="blocker",
                    node=node.id,
                    summary=f"Baseline data does not prove {app.name!r} is installed",
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "version": app.version,
                        "source": app.source,
                    },
                )
            elif action.source == "baseline":
                context.add_gap(
                    gap_id="ACTION_INSTALLATION_UNVERIFIED",
                    severity="blocker",
                    node=node.id,
                    summary=(
                        f"Baseline action {action.name!r} was not verified in "
                        f"installed app {app.name!r}"
                    ),
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "app_version": app.version,
                        "source": action.source,
                    },
                )
            if app.name.casefold() == "phantom":
                context.add_gap(
                    gap_id="BUILTIN_ACTION_COMPILER_UNQUALIFIED",
                    severity="blocker",
                    node=node.id,
                    summary="SOAR-native action needs an explicit compiler mapping",
                    detail={"app": app.name, "action": action.name},
                )
