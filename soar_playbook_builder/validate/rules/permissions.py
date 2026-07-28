"""Action permission evidence rules."""

from __future__ import annotations

from ir.schema import ActionNode

from .base import ValidationContext, action_permission_key, normalize


class PermissionRule:
    def run(self, context: ValidationContext) -> None:
        permissions = {
            normalize(key): value
            for key, value in context.index.action_permissions.items()
        }
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            action = context.resolved_actions.get(node.id)
            app = context.resolved_apps.get(node.id)
            if action is None or app is None:
                continue
            key = normalize(action_permission_key(app.name, action.name))
            status = permissions.get(key, "unknown")
            if context.index.permissions_status != "verified" or status == "unknown":
                context.add_gap(
                    gap_id="PERMISSION_UNVERIFIED",
                    severity="blocker",
                    node=node.id,
                    summary="Executing-principal permission is not verified",
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "principal": context.index.permission_principal,
                        "roles": sorted(context.index.roles),
                        "evidence_status": context.index.permissions_status,
                    },
                )
            elif status == "denied":
                context.add_gap(
                    gap_id="PERMISSION_DENIED",
                    severity="blocker",
                    node=node.id,
                    summary="Executing principal is denied this action",
                    detail={
                        "app": app.name,
                        "action": action.name,
                        "principal": context.index.permission_principal,
                        "roles": sorted(context.index.roles),
                    },
                )
