"""Asset existence, connector ownership, configuration, and health rules."""

from __future__ import annotations

from ir.schema import ActionNode, BoundAsset

from .base import ValidationContext, normalize


def _asset_matches_app(asset: object, app_names: set[str]) -> bool:
    authoritative = {
        normalize(str(getattr(asset, "app", ""))),
        normalize(str(getattr(asset, "product_code", ""))),
    }
    authoritative.discard("")
    if authoritative:
        return bool(authoritative & app_names)
    product_name = normalize(str(getattr(asset, "product_name", "")))
    return bool(product_name and product_name in app_names)


class AssetBindingRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            if not isinstance(node, ActionNode):
                continue
            app = context.resolved_apps.get(node.id)
            if app is None or app.name.casefold() == "phantom":
                continue
            app_names = {
                normalize(app.name),
                normalize(app.product_name),
                normalize(node.app),
            }
            candidates = sorted(
                (
                    asset.name
                    for asset in context.index.assets
                    if _asset_matches_app(asset, app_names)
                ),
                key=str.casefold,
            )
            if not isinstance(node.asset, BoundAsset):
                context.add_gap(
                    gap_id="ASSET_UNBOUND",
                    severity="blocker",
                    node=node.id,
                    summary=f"Action {node.action!r} has no explicit asset",
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "candidate_assets": candidates,
                        "required_config_keys": sorted(app.configuration_keys),
                    },
                )
                continue
            bound_name = normalize(node.asset.name)
            asset = next(
                (
                    item
                    for item in sorted(
                        context.index.assets,
                        key=lambda row: row.name.casefold(),
                    )
                    if normalize(item.name) == bound_name
                ),
                None,
            )
            if asset is None:
                context.add_gap(
                    gap_id="ASSET_MISSING",
                    severity="blocker",
                    node=node.id,
                    summary=f"Bound asset {node.asset.name!r} does not exist",
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "asset": node.asset.name,
                        "candidate_assets": candidates,
                        "required_config_keys": sorted(app.configuration_keys),
                    },
                )
                continue
            if not _asset_matches_app(asset, app_names):
                context.add_gap(
                    gap_id="ASSET_APP_MISMATCH",
                    severity="blocker",
                    node=node.id,
                    summary=(
                        f"Asset {asset.name!r} is not associated with app {app.name!r}"
                    ),
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "asset": asset.name,
                        "asset_app": asset.app,
                        "asset_product": asset.product_name,
                    },
                )
            if not asset.configured:
                context.add_gap(
                    gap_id="ASSET_NOT_CONFIGURED",
                    severity="blocker",
                    node=node.id,
                    summary=f"Asset {asset.name!r} is not fully configured",
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "asset": asset.name,
                        "required_config_keys": sorted(app.configuration_keys),
                    },
                )
            if not asset.healthy:
                context.add_gap(
                    gap_id="ASSET_UNHEALTHY",
                    severity="blocker",
                    node=node.id,
                    summary=f"Asset {asset.name!r} is not healthy",
                    detail={
                        "app": app.name,
                        "action": node.action,
                        "asset": asset.name,
                    },
                )
