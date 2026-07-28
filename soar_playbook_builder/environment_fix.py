"""One-click environment fixes — auto-discover and persist asset_defaults on the PB asset."""

from __future__ import annotations

import json
from typing import Any

from asset_resolver import (
    ASSET_TYPE_HINTS,
    _asset_field,
    _candidate_assets,
    fetch_configured_assets,
    parse_asset_defaults,
)
from soar_rest import django_request_rest, phantom_rest_call

# Scaffold keys we try to map from installed SOAR assets (lab-friendly order).
DISCOVERY_KEYS: tuple[str, ...] = (
    "soar",
    "okta",
    "slack",
    "servicenow",
    "splunk_enterprise",
    "panw",
    "virustotalv3",
    "active_directory",
    "clearpass_cppm",
)


def discover_suggested_defaults(request: Any | None) -> dict[str, str]:
    """Map scaffold keys → configured asset names when there is a single unambiguous match."""
    configured = fetch_configured_assets(request)
    suggested: dict[str, str] = {}
    for key in DISCOVERY_KEYS:
        if key not in ASSET_TYPE_HINTS and key != "soar":
            continue
        candidates = _candidate_assets(key, configured)
        if len(candidates) == 1:
            name = _asset_field(candidates[0], "name")
            if name:
                suggested[key] = name
    return suggested


def _parse_configuration_blob(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def _find_asset_record(request: Any, *, asset_id: int | None, asset_name: str) -> dict[str, Any] | None:
    if asset_id is not None:
        ok, resp, _ = django_request_rest(request, "GET", f"asset/{asset_id}")
        if ok and isinstance(resp, dict) and resp.get("id") is not None:
            return resp
        ok, resp = phantom_rest_call("GET", f"asset/{asset_id}", request=request)
        if ok and isinstance(resp, dict) and resp.get("id") is not None:
            return resp

    for record in fetch_configured_assets(request):
        if asset_name and _asset_field(record, "name") == asset_name:
            return record
        if asset_id is not None and str(record.get("id")) == str(asset_id):
            return record
    return None


def _current_pb_asset(request: Any, asset_name_hint: str = "") -> tuple[int | None, str, dict[str, Any]]:
    record: dict[str, Any] = {}
    try:
        import phantom.app as phantom  # noqa: PLC0415

        record = dict(phantom.get_current_asset() or {})
    except Exception:  # noqa: BLE001
        record = {}

    aid = record.get("id")
    name = _asset_field(record, "name") or asset_name_hint
    if aid is None and name:
        fetched = _find_asset_record(request, asset_id=None, asset_name=name)
        if fetched:
            record = fetched
            aid = fetched.get("id")
    return (int(aid) if aid is not None else None), name, record


def _merge_defaults(existing: dict[str, str], discovered: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    merged = dict(existing)
    added: list[str] = []
    for key, val in discovered.items():
        if key not in merged:
            merged[key] = val
            added.append(f"{key}→{val}")
    return merged, added


def _post_asset_update(request: Any, asset_id: int, body: dict[str, Any]) -> tuple[bool, str]:
    paths = (f"asset/{asset_id}", "asset")
    last_err = "Asset update failed"
    for path in paths:
        ok, resp, _ = django_request_rest(request, "POST", path, body=body)
        if ok:
            return True, ""
        last_err = str(resp)
        ok, resp = phantom_rest_call("POST", path, body=body, request=request)
        if ok:
            return True, ""
        last_err = str(resp)
    return False, last_err


def persist_asset_defaults(
    request: Any,
    *,
    asset_id: int | None,
    asset_name: str,
    defaults: dict[str, str],
) -> tuple[bool, str]:
    """Write asset_defaults JSON onto the Playbook Builder asset (full configuration preserved)."""
    record = _find_asset_record(request, asset_id=asset_id, asset_name=asset_name)
    if not record:
        return False, f"Playbook Builder asset not found ({asset_name or asset_id})."

    aid = int(record.get("id") or asset_id or 0)
    if not aid:
        return False, "Asset id missing — cannot update configuration."

    configuration = _parse_configuration_blob(record.get("configuration"))
    for key, val in record.items():
        if key == "configuration":
            continue
        if key in configuration or not str(val or "").strip():
            continue
        if key in {
            "mcp_bridge_url",
            "mcp_bridge_allow_insecure_http",
            "soar_loopback_allow_insecure_tls",
            "soar_loopback_ca_bundle",
            "ai_instructions",
            "asset_defaults",
            "custom_templates_json",
            "custom_ir_templates_json",
            "allow_legacy_python_templates",
            "playbook_defaults_json",
            "es_web_url",
            "sample_cases_json",
            "soar_rest_token",
        }:
            configuration.setdefault(key, val)

    configuration["asset_defaults"] = json.dumps(defaults, separators=(",", ":"))
    body = {
        "id": aid,
        "name": _asset_field(record, "name") or asset_name,
        "configuration": configuration,
    }
    for field in (
        "description",
        "product_name",
        "product_vendor",
        "type",
        "app_id",
        "app_guid",
        "primary_owners",
        "secondary_users",
        "tags",
    ):
        if record.get(field) is not None:
            body[field] = record[field]

    ok, err = _post_asset_update(request, aid, body)
    if not ok:
        return False, err or "SOAR rejected asset update (check asset owner permissions)."
    return True, ""


def apply_environment_fixes_payload(
    request: Any,
    cfg: dict[str, Any],
    *,
    confirm: bool = False,
    asset_name_hint: str = "",
) -> dict[str, Any]:
    """Preview or apply safe environment fixes (asset_defaults auto-map)."""
    existing = parse_asset_defaults(cfg.get("asset_defaults"))
    discovered = discover_suggested_defaults(request)
    merged, added = _merge_defaults(existing, discovered)

    if not added and existing:
        return {
            "status": "success",
            "message": "Asset defaults already configured.",
            "asset_defaults": json.dumps(existing, separators=(",", ":")),
            "checks": [
                {
                    "id": "asset_defaults",
                    "severity": "ok",
                    "title": "Asset defaults",
                    "detail": ", ".join(f"{k}→{v}" for k, v in sorted(existing.items())[:8]),
                }
            ],
        }

    if not merged:
        return {
            "status": "needs_attention",
            "message": (
                "No integration assets found to auto-map. "
                "Create assets under Apps (e.g. Okta, Slack) then retry Fix environment."
            ),
            "suggested_asset_defaults": {},
            "troubleshooting": {
                "id": "no_assets_for_defaults",
                "title": "No assets to map",
                "severity": "warn",
                "symptom": "Fix environment found zero mappable integrations",
                "cause": "SOAR has no configured assets matching common template keys.",
                "fix_steps": [
                    "Create assets: Okta, Slack, ServiceNow, Splunk SOAR (phantom), etc.",
                    "Name them simply (okta, slack, snow_lab) or use lab conventions.",
                    "Click Fix environment again to auto-fill asset_defaults.",
                ],
                "verify": "environment_check shows Asset defaults as ok",
            },
        }

    preview_json = json.dumps(merged, separators=(",", ":"))
    if not confirm:
        return {
            "status": "success",
            "needs_confirm": True,
            "message": f"Apply asset_defaults on this Playbook Builder asset?\n\n`{preview_json}`",
            "proposed_asset_defaults": merged,
            "proposed_additions": added,
            "suggested_asset_defaults": discovered,
            "fixes": [
                {
                    "id": "apply_asset_defaults",
                    "label": "Apply asset defaults",
                    "action": "apply_environment_fixes",
                }
            ],
        }

    asset_id, asset_name, _ = _current_pb_asset(request, asset_name_hint)
    ok, err = persist_asset_defaults(
        request,
        asset_id=asset_id,
        asset_name=asset_name or asset_name_hint,
        defaults=merged,
    )
    if not ok:
        return {
            "status": "error",
            "error": err,
            "proposed_asset_defaults": merged,
        }

    cfg["asset_defaults"] = preview_json
    if hasattr(request, "_pb_config") and isinstance(request._pb_config, dict):  # noqa: SLF001
        request._pb_config["asset_defaults"] = preview_json  # noqa: SLF001

    return {
        "status": "success",
        "message": f"Applied asset_defaults: {', '.join(added) or preview_json}",
        "fixes_applied": [f"asset_defaults: {', '.join(added) or preview_json}"],
        "asset_defaults": preview_json,
        "proposed_asset_defaults": merged,
    }
