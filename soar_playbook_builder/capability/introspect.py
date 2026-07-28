"""Harvest SOAR capabilities from local REST API only — no external network."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from capability.schema import (
    ActionCapability,
    ActionParameter,
    AppCapability,
    AssetRecord,
    CefField,
    CapabilityIndex,
    EgressTag,
)
from soar_rest import phantom_rest_call

RestFn = Callable[..., tuple[bool, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rows_from_rest(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    if isinstance(resp, dict):
        for key in ("data", "items", "results", "apps", "assets"):
            data = resp.get(key)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
            if isinstance(data, dict) and data.get("id") is not None:
                return [data]
        if resp.get("id") is not None or resp.get("name"):
            return [resp]
    return []


def _egress_for(app: str, action: str, egress_map: dict[str, dict[str, str]]) -> EgressTag:
    app_tags = egress_map.get(app) or egress_map.get(app.lower()) or {}
    tag = app_tags.get(action) or app_tags.get(action.lower())
    if tag in ("true", "false", "unknown"):
        return tag  # type: ignore[return-value]
    return "unknown"


def _parse_action_rows(app_name: str, rows: list[dict[str, Any]], egress_map: dict[str, dict[str, str]]) -> list[ActionCapability]:
    actions: list[ActionCapability] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("action") or row.get("name") or "").strip()
        if not name:
            continue
        params: list[ActionParameter] = []
        for param in row.get("parameters") or row.get("params") or []:
            if isinstance(param, dict):
                params.append(ActionParameter.from_rest(param))
        outputs = row.get("output") or row.get("output_datapaths") or []
        if isinstance(outputs, list):
            output_paths = [
                str(o.get("data_path") if isinstance(o, dict) else o)
                for o in outputs
                if o
            ]
        else:
            output_paths = []
        actions.append(
            ActionCapability(
                name=name,
                app=app_name,
                description=str(row.get("description") or ""),
                parameters=params,
                output_datapaths=output_paths,
                requires_egress=_egress_for(app_name, name, egress_map),
                source="discovered",
            )
        )
    return actions


def harvest_apps(
    rest_fn: RestFn | None = None,
    *,
    request: Any | None = None,
    egress_map: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, AppCapability], list[str]]:
    """Return installed apps + actions from SOAR REST."""
    errors: list[str] = []
    egress_map = egress_map or {}
    apps: dict[str, AppCapability] = {}

    def _call(method: str, path: str, **kwargs: Any) -> tuple[bool, Any]:
        if rest_fn is not None:
            return rest_fn(method, path, **kwargs)
        return phantom_rest_call(method, path, request=request, **kwargs)

    ok, resp = _call("GET", "app", params={"page_size": 500})
    if not ok:
        errors.append(f"app list: {resp}")
        return apps, errors

    for app_row in _rows_from_rest(resp):
        name = str(app_row.get("name") or app_row.get("product_name") or "").strip()
        if not name:
            continue
        version = str(app_row.get("version") or app_row.get("app_version") or "")
        product_name = str(app_row.get("product_name") or app_row.get("label") or name)
        actions: list[ActionCapability] = []

        detail_ok, detail = _call("GET", f"app/{name}")
        if detail_ok:
            detail_row = detail if isinstance(detail, dict) else {}
            if isinstance(detail, list) and detail:
                detail_row = detail[0] if isinstance(detail[0], dict) else {}
            action_rows = detail_row.get("actions") or detail_row.get("action_list") or []
            if isinstance(action_rows, list):
                actions = _parse_action_rows(name, action_rows, egress_map)
        else:
            inline = app_row.get("actions") or []
            if isinstance(inline, list) and inline:
                actions = _parse_action_rows(name, inline, egress_map)
            else:
                errors.append(f"app/{name}: {detail}")

        apps[name] = AppCapability(
            name=name,
            product_name=product_name,
            version=version,
            actions=actions,
            source="discovered",
            last_verified=_utc_now(),
        )
    return apps, errors


def harvest_assets(
    rest_fn: RestFn | None = None,
    *,
    request: Any | None = None,
) -> tuple[list[AssetRecord], list[str]]:
    errors: list[str] = []
    assets: list[AssetRecord] = []

    def _call(method: str, path: str, **kwargs: Any) -> tuple[bool, Any]:
        if rest_fn is not None:
            return rest_fn(method, path, **kwargs)
        return phantom_rest_call(method, path, request=request, **kwargs)

    ok, resp = _call("GET", "asset", params={"page_size": 500})
    if not ok:
        errors.append(f"asset list: {resp}")
        return assets, errors

    for row in _rows_from_rest(resp):
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        product_name = str(row.get("product_name") or "")
        product_code = str(row.get("product_code") or row.get("product_vendor") or "")
        configured = bool(row.get("id"))
        healthy = str(row.get("status") or "success").lower() in ("success", "active", "online", "")
        assets.append(
            AssetRecord(
                name=name,
                app=str(row.get("app") or row.get("app_name") or product_code),
                product_name=product_name,
                product_code=product_code,
                configured=configured,
                healthy=healthy,
                id=row.get("id"),
            )
        )
    return assets, errors


def harvest_vocabularies(
    rest_fn: RestFn | None = None,
    *,
    request: Any | None = None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return labels, severities, statuses, and errors from SOAR REST where available."""
    errors: list[str] = []
    labels: list[str] = []
    severities: list[str] = []
    statuses: list[str] = []

    def _call(method: str, path: str, **kwargs: Any) -> tuple[bool, Any]:
        if rest_fn is not None:
            return rest_fn(method, path, **kwargs)
        return phantom_rest_call(method, path, request=request, **kwargs)

    ok, resp = _call("GET", "container_label", params={"page_size": 500})
    if ok:
        for row in _rows_from_rest(resp):
            val = str(row.get("name") or row.get("label") or "").strip()
            if val:
                labels.append(val)
    else:
        errors.append(f"container_label: {resp}")

    ok, resp = _call("GET", "severity", params={"page_size": 100})
    if ok:
        for row in _rows_from_rest(resp):
            val = str(row.get("name") or row.get("severity") or "").strip()
            if val:
                severities.append(val)
    else:
        errors.append(f"severity: {resp}")

    ok, resp = _call("GET", "status", params={"page_size": 100})
    if ok:
        for row in _rows_from_rest(resp):
            val = str(row.get("name") or row.get("status") or "").strip()
            if val:
                statuses.append(val)
    else:
        errors.append(f"status: {resp}")

    return labels, severities, statuses, errors


def harvest_all(
    rest_fn: RestFn | None = None,
    *,
    request: Any | None = None,
    egress_map: dict[str, dict[str, str]] | None = None,
    baseline_cef: list[CefField] | None = None,
) -> CapabilityIndex:
    """Full harvest; merges baseline CEF when live catalog is unavailable."""
    errors: list[str] = []
    apps, app_errors = harvest_apps(rest_fn, request=request, egress_map=egress_map)
    errors.extend(app_errors)
    assets, asset_errors = harvest_assets(rest_fn, request=request)
    errors.extend(asset_errors)
    labels, severities, statuses, vocab_errors = harvest_vocabularies(rest_fn, request=request)
    errors.extend(vocab_errors)

    cef_fields = list(baseline_cef or [])
    status: str = "ok"
    if errors and apps:
        status = "partial"
    elif errors and not apps:
        status = "failed"

    return CapabilityIndex(
        built_at=_utc_now(),
        harvest_status=status,  # type: ignore[arg-type]
        harvest_errors=errors,
        apps=apps,
        assets=assets,
        cef_fields=cef_fields,
        labels=sorted(set(labels)),
        severities=sorted(set(severities)) or ["low", "medium", "high", "critical"],
        statuses=sorted(set(statuses)) or ["new", "open", "closed"],
    )
