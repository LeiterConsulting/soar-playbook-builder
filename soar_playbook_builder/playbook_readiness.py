"""Playbook readiness: validate gaps (code, assets, container, variables) and auto-fix where safe."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from builder_helpers import analyze_playbook, preview_blocks_from_source
from preview_visual import attach_visual_preview, extract_phantom_acts

from asset_resolver import (
    apply_asset_map_to_source,
    build_asset_preflight,
    parse_asset_defaults,
)

_PLACEHOLDER_RE = re.compile(
    r"(TODO|CHANGEME|YOUR_|REPLACE_ME|<\w+>|example\.com|slack_lab|#your-)",
    re.IGNORECASE,
)
_CONST_ASSIGN_RE = re.compile(
    r"^([A-Z][A-Z0-9_]{2,})\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_CALLBACK_RE = re.compile(r"callback\s*=\s*(\w+)")
_FUNC_DEF_RE = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)
_DATAPATH_RE = re.compile(r"['\"](artifact:[^'\"]+|container:[^'\"]+)['\"]")


def parse_playbook_defaults(raw: Any) -> dict[str, Any]:
    """Parse asset `playbook_defaults_json` — constants and asset aliases for auto-fill."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _container_id_from_request(request: Any | None) -> int | None:
    if request is None:
        return None
    raw = request.GET.get("container_id") if hasattr(request, "GET") else None
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _check_callbacks(source: str) -> list[str]:
    callbacks = set(_CALLBACK_RE.findall(source or ""))
    funcs = set(_FUNC_DEF_RE.findall(source or ""))
    missing = sorted(callbacks - funcs - {"None", "on_finish"})
    return missing


def _check_placeholders(source: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for match in _CONST_ASSIGN_RE.finditer(source or ""):
        name, value = match.group(1), match.group(2)
        if _PLACEHOLDER_RE.search(value) or value.lower() in {"tbd", "changeme", "xxx"}:
            found.append({"name": name, "value": value})
    return found


def _artifact_keys_from_datapaths(datapaths: list[str]) -> set[str]:
    keys: set[str] = set()
    for path in datapaths:
        if path.startswith("container:"):
            keys.add(path.split(":", 1)[1])
            continue
        if "cef." in path:
            keys.add(path.rsplit("cef.", 1)[-1])
    return keys


def build_readiness_report(
    source: str,
    request: Any | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    asset_overrides: dict[str, str] | None = None,
    linked_playbook_id: str | int | None = None,
    attempts_log: list[str] | None = None,
) -> dict[str, Any]:
    """Full readiness checklist for current draft + SOAR environment."""
    cfg = cfg or {}
    source = source or ""
    analysis = analyze_playbook(source)
    acts = extract_phantom_acts(source)
    datapaths = analysis.get("datapaths") or _DATAPATH_RE.findall(source)

    asset_defaults = parse_asset_defaults(cfg.get("asset_defaults"))
    playbook_defaults = parse_playbook_defaults(cfg.get("playbook_defaults_json"))
    default_constants = playbook_defaults.get("constants") if isinstance(
        playbook_defaults.get("constants"), dict
    ) else {}

    preflight = build_asset_preflight(
        source,
        request,
        overrides=asset_overrides,
        defaults=asset_defaults,
        attempts_log=attempts_log,
    )

    items: list[dict[str, Any]] = []

    if not analysis.get("valid_python"):
        items.append(
            {
                "id": "invalid_python",
                "category": "code",
                "severity": "error",
                "title": "Invalid Python",
                "detail": (analysis.get("findings") or [{}])[0].get("message", "Syntax error"),
                "auto_fixable": False,
            }
        )
    else:
        if "on_start" not in (analysis.get("functions") or []):
            items.append(
                {
                    "id": "missing_on_start",
                    "category": "code",
                    "severity": "error",
                    "title": "Missing on_start(container)",
                    "detail": "SOAR playbooks must define on_start(container).",
                    "auto_fixable": False,
                }
            )
        if analysis.get("act_count", 0) == 0:
            items.append(
                {
                    "id": "no_phantom_act",
                    "category": "code",
                    "severity": "error",
                    "title": "No integration actions",
                    "detail": (
                        "This draft has 0 phantom.act() calls — nothing will call Slack, Okta, "
                        "firewall, etc. Review Code tab or refine your NL prompt."
                    ),
                    "auto_fixable": False,
                }
            )
        missing_cb = _check_callbacks(source)
        if missing_cb:
            items.append(
                {
                    "id": "missing_callbacks",
                    "category": "code",
                    "severity": "error",
                    "title": "Missing callback functions",
                    "detail": f"Referenced but not defined: {', '.join(missing_cb)}",
                    "auto_fixable": False,
                }
            )

    for req in preflight.get("requirements") or []:
        status = req.get("status")
        key = req.get("key", "")
        if status == "resolved":
            continue
        sev = "error" if status == "missing" else "warn"
        items.append(
            {
                "id": f"asset_{key}",
                "category": "integrations",
                "severity": sev,
                "title": f"Integration: {req.get('label') or key}",
                "detail": req.get("resolution") or status,
                "auto_fixable": status == "ambiguous" or (
                    status == "missing" and key in asset_defaults
                ),
                "fix_id": "map_assets" if status in ("ambiguous", "resolved", "invalid_override") else None,
                "requirement_key": key,
            }
        )

    if preflight.get("asset_map"):
        unmapped_in_source = []
        for act in acts:
            for asset_key in act.get("assets") or []:
                mapped = preflight["asset_map"].get(asset_key)
                if mapped and mapped != asset_key:
                    unmapped_in_source.append(asset_key)
        if unmapped_in_source:
            items.append(
                {
                    "id": "asset_map_pending",
                    "category": "integrations",
                    "severity": "info",
                    "title": "Asset names can be auto-mapped",
                    "detail": (
                        f"Source uses scaffold keys {sorted(set(unmapped_in_source))} — "
                        "click Apply fixes to rewrite to configured SOAR asset names."
                    ),
                    "auto_fixable": True,
                    "fix_id": "map_assets",
                }
            )

    placeholders = _check_placeholders(source)
    for ph in placeholders:
        const_name = ph["name"]
        has_default = const_name in default_constants
        items.append(
            {
                "id": f"placeholder_{const_name}",
                "category": "variables",
                "severity": "warn",
                "title": f"Placeholder constant: {const_name}",
                "detail": f'Current value "{ph["value"]}" looks like a placeholder.',
                "auto_fixable": has_default,
                "fix_id": "apply_constants" if has_default else None,
                "constant_name": const_name,
                "suggested_value": default_constants.get(const_name) if has_default else None,
            }
        )

    container_id = _container_id_from_request(request)
    uses_container_fields = any(p.startswith("container:") for p in datapaths)
    if uses_container_fields or acts:
        if container_id:
            items.append(
                {
                    "id": "container_linked",
                    "category": "run",
                    "severity": "info",
                    "title": "Container context present",
                    "detail": f"Sidecar linked to case {container_id} — Run on this case is available after import.",
                    "auto_fixable": False,
                }
            )
            try:
                from investigation_context import _fetch_artifacts, _fetch_container

                container, _ = _fetch_container(container_id, request)
                artifacts, _ = _fetch_artifacts(container_id, request)
                if container:
                    sev = (container.get("severity") or "unknown").lower()
                    items.append(
                        {
                            "id": "container_severity",
                            "category": "run",
                            "severity": "info",
                            "title": "Container severity",
                            "detail": f'Current severity: "{sev}" — conditional branches use this at runtime.',
                            "auto_fixable": False,
                        }
                    )
                wanted = _artifact_keys_from_datapaths(datapaths)
                if wanted and not artifacts:
                    items.append(
                        {
                            "id": "no_artifacts",
                            "category": "run",
                            "severity": "warn",
                            "title": "No artifacts on container",
                            "detail": (
                                f"Playbook collects {sorted(wanted)} but container {container_id} "
                                "has no artifacts — collect steps may return empty."
                            ),
                            "auto_fixable": False,
                        }
                    )
            except Exception:  # noqa: BLE001
                pass
        else:
            items.append(
                {
                    "id": "container_missing",
                    "category": "run",
                    "severity": "warn",
                    "title": "No case linked",
                    "detail": (
                        "Open Playbook Builder from a SOAR case using get sidecar url with container_id, "
                        "or run the playbook from the case Playbooks tab after import."
                    ),
                    "auto_fixable": False,
                }
            )

    if linked_playbook_id:
        items.append(
            {
                "id": "playbook_imported",
                "category": "run",
                "severity": "info",
                "title": "Playbook imported",
                "detail": f"Linked playbook id {linked_playbook_id}.",
                "auto_fixable": False,
            }
        )

    errors = [i for i in items if i.get("severity") == "error"]
    warnings = [i for i in items if i.get("severity") == "warn"]
    fixable = [i for i in items if i.get("auto_fixable")]

    ready = not errors and preflight.get("ready", True)

    return {
        "ready": ready,
        "ready_for_import": ready and not any(i["id"] == "no_phantom_act" for i in errors),
        "ready_for_run": ready and bool(container_id) and bool(linked_playbook_id),
        "items": items,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "auto_fix_count": len(fixable),
        "asset_preflight": preflight,
        "analysis": analysis,
        "available_fixes": sorted({i["fix_id"] for i in fixable if i.get("fix_id")}),
    }


def apply_readiness_fixes(
    source: str,
    report: dict[str, Any],
    *,
    cfg: dict[str, Any] | None = None,
    fix_ids: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Apply safe auto-fixes; returns (updated_source, descriptions)."""
    cfg = cfg or {}
    fix_ids = fix_ids or report.get("available_fixes") or []
    applied: list[str] = []
    updated = source

    playbook_defaults = parse_playbook_defaults(cfg.get("playbook_defaults_json"))
    default_constants = playbook_defaults.get("constants") if isinstance(
        playbook_defaults.get("constants"), dict
    ) else {}

    if "map_assets" in fix_ids:
        asset_map = dict((report.get("asset_preflight") or {}).get("asset_map") or {})
        asset_defaults = parse_asset_defaults(cfg.get("asset_defaults"))
        pb_assets = playbook_defaults.get("assets") if isinstance(
            playbook_defaults.get("assets"), dict
        ) else {}
        merged = {**asset_defaults, **{str(k): str(v) for k, v in pb_assets.items()}, **asset_map}
        if merged:
            new_source = apply_asset_map_to_source(updated, merged)
            if new_source != updated:
                applied.append(f"Mapped integration assets: {merged}")
                updated = new_source

    if "apply_constants" in fix_ids and default_constants:
        for name, value in default_constants.items():
            pattern = rf"^({re.escape(name)}\s*=\s*)['\"][^'\"]*['\"]"
            repl = rf'\1"{value}"'
            new_source, n = re.subn(pattern, repl, updated, count=1, flags=re.MULTILINE)
            if n:
                applied.append(f'Set constant {name} = "{value}"')
                updated = new_source

    return updated, applied


def readiness_payload_from_source(
    source: str,
    request: Any | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    asset_overrides: dict[str, str] | None = None,
    linked_playbook_id: str | int | None = None,
    apply_fixes: bool = False,
    fix_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build readiness report; optionally apply fixes and refresh preview."""
    attempts: list[str] = []
    report = build_readiness_report(
        source,
        request,
        cfg=cfg,
        asset_overrides=asset_overrides,
        linked_playbook_id=linked_playbook_id,
        attempts_log=attempts,
    )
    result: dict[str, Any] = {
        "status": "success" if report.get("ready_for_import") else "needs_attention",
        "readiness": report,
        "source": source,
        "import_attempts": attempts,
    }

    if apply_fixes and report.get("available_fixes"):
        fixed_source, applied = apply_readiness_fixes(
            source, report, cfg=cfg, fix_ids=fix_ids
        )
        if applied:
            result["fixes_applied"] = applied
            result["source"] = fixed_source
            result["analysis"] = analyze_playbook(fixed_source)
            result["preview"] = preview_blocks_from_source(fixed_source)
            result = attach_visual_preview(result)
            report = build_readiness_report(
                fixed_source,
                request,
                cfg=cfg,
                asset_overrides=asset_overrides,
                linked_playbook_id=linked_playbook_id,
            )
            result["readiness"] = report
            result["status"] = "success" if report.get("ready_for_import") else "needs_attention"

    lines = ["**Readiness check**"]
    if report.get("ready_for_import"):
        lines.append("Ready for import.")
    else:
        lines.append("Fix items below before import (or apply auto-fixes where offered).")
    for item in report.get("items") or []:
        if item.get("severity") in ("error", "warn"):
            icon = "❌" if item["severity"] == "error" else "⚠️"
            lines.append(f"{icon} **{item.get('title')}** — {item.get('detail')}")
    result["content"] = "\n".join(lines)
    return result
