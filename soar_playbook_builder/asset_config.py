"""Export and import Playbook Builder asset configuration for migration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from environment_fix import (
    _current_pb_asset,
    _find_asset_record,
    _parse_configuration_blob,
    _post_asset_update,
)
from asset_resolver import _asset_field

EXPORT_VERSION = "1.0"
EXPORTABLE_KEYS: tuple[str, ...] = (
    "mcp_bridge_url",
    "ai_instructions",
    "asset_defaults",
    "custom_templates_json",
    "playbook_defaults_json",
    "es_web_url",
    "sample_cases_json",
    "operating_mode",
    "default_ui_mode",
    "phenv_use_sudo",
    "phenv_path",
)
SECRET_KEYS: frozenset[str] = frozenset({"soar_rest_token"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def configuration_from_cfg(cfg: dict[str, Any], *, include_secrets: bool = False) -> dict[str, str]:
    """Extract allowlisted configuration fields from sidecar cfg dict."""
    out: dict[str, str] = {}
    for key in EXPORTABLE_KEYS:
        raw = cfg.get(key)
        if raw is None:
            continue
        val = str(raw).strip()
        if val:
            out[key] = val
    if include_secrets:
        token = str(cfg.get("soar_rest_token") or "").strip()
        if token:
            out["soar_rest_token"] = token
    elif cfg.get("soar_rest_token"):
        out["soar_rest_token"] = "***REDACTED***"
    return out


def export_asset_config_payload(
    cfg: dict[str, Any],
    *,
    include_secrets: bool = False,
    sidecar_url: str = "",
) -> dict[str, Any]:
    """Return migration-friendly JSON bundle (secrets redacted by default)."""
    configuration = configuration_from_cfg(cfg, include_secrets=include_secrets)
    bundle = {
        "export_version": EXPORT_VERSION,
        "exported_at": _utc_now(),
        "app": "soar_playbook_builder",
        "configuration": configuration,
    }
    copy_json = json.dumps(bundle, indent=2, sort_keys=True)
    return {
        "status": "success",
        "message": "Asset configuration exported — save copy_json before migrating SOAR instances.",
        "export_version": EXPORT_VERSION,
        "exported_at": bundle["exported_at"],
        "configuration": configuration,
        "secrets_redacted": not include_secrets and bool(cfg.get("soar_rest_token")),
        "sidecar_url": sidecar_url,
        "copy_json": copy_json,
        "field_count": len(configuration),
    }


def _merge_import_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for key in EXPORTABLE_KEYS:
        if key in incoming and incoming[key] is not None:
            val = str(incoming[key]).strip()
            if val and val != "***REDACTED***":
                merged[key] = val
        elif key in existing and existing[key] is not None:
            merged[key] = str(existing[key])
    if "soar_rest_token" in incoming:
        token = str(incoming["soar_rest_token"]).strip()
        if token and token != "***REDACTED***":
            merged["soar_rest_token"] = token
    return merged


def persist_asset_configuration(
    request: Any,
    *,
    asset_id: int | None,
    asset_name: str,
    configuration: dict[str, str],
) -> tuple[bool, str]:
    """Write allowlisted keys onto the Playbook Builder asset."""
    record = _find_asset_record(request, asset_id=asset_id, asset_name=asset_name)
    if not record and asset_id:
        record = {"id": asset_id, "name": asset_name}
    if not record:
        return False, f"Playbook Builder asset not found ({asset_name or asset_id})."

    aid = int(record.get("id") or asset_id or 0)
    if not aid:
        return False, "Asset id missing — cannot update configuration."

    current = _parse_configuration_blob(record.get("configuration"))
    for key, val in record.items():
        if key == "configuration":
            continue
        if key in current or not str(val or "").strip():
            continue
        if key in EXPORTABLE_KEYS or key in SECRET_KEYS:
            current.setdefault(key, val)

    for key, val in configuration.items():
        if key in EXPORTABLE_KEYS or key in SECRET_KEYS:
            current[key] = val

    body = {
        "id": aid,
        "name": _asset_field(record, "name") or asset_name,
        "configuration": current,
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
        return False, err or "SOAR rejected asset update."
    return True, ""


def import_asset_config_payload(
    request: Any,
    cfg: dict[str, Any],
    *,
    config_json: str | dict[str, Any] | None = None,
    confirm: bool = False,
    asset_name_hint: str = "",
) -> dict[str, Any]:
    """Preview or apply imported asset configuration."""
    if not config_json:
        return {
            "status": "error",
            "error": "config_json required — paste export bundle or configuration object.",
        }

    try:
        if isinstance(config_json, dict):
            blob = config_json
        else:
            blob = json.loads(str(config_json))
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid JSON: {exc}"}

    incoming = blob.get("configuration") if isinstance(blob.get("configuration"), dict) else blob
    if not isinstance(incoming, dict):
        return {"status": "error", "error": "Expected configuration object in export bundle."}

    proposed = _merge_import_config(cfg, incoming)
    if not proposed:
        return {"status": "error", "error": "No allowlisted configuration keys found in import."}

    preview_keys = sorted(proposed.keys())
    if not confirm:
        return {
            "status": "success",
            "needs_confirm": True,
            "message": f"Apply {len(preview_keys)} configuration field(s)? Keys: {', '.join(preview_keys)}",
            "proposed_configuration": proposed,
            "import_keys": preview_keys,
        }

    asset_id, asset_name, _ = _current_pb_asset(request, asset_name_hint)
    ok, err = persist_asset_configuration(
        request,
        asset_id=asset_id,
        asset_name=asset_name or asset_name_hint,
        configuration=proposed,
    )
    if not ok:
        return {"status": "error", "error": err, "proposed_configuration": proposed}

    if hasattr(request, "_pb_config") and isinstance(request._pb_config, dict):  # noqa: SLF001
        request._pb_config.update(proposed)  # noqa: SLF001

    return {
        "status": "success",
        "message": f"Imported configuration: {', '.join(preview_keys)}",
        "fixes_applied": [f"configuration: {', '.join(preview_keys)}"],
        "proposed_configuration": proposed,
        "import_keys": preview_keys,
    }
