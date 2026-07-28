"""NL / MCP environment readiness — checks and suggested fix actions for the sidecar."""

from __future__ import annotations

from typing import Any

from asset_resolver import parse_asset_defaults
from capability.index import index_status
from environment_fix import discover_suggested_defaults
from pattern_catalog import list_patterns_payload
from runtime_fixtures import RUNTIME_FIXTURES


def _probe_bridge(mcp_bridge_url: str) -> dict[str, Any]:
    from playbook_builder_connector import _probe_mcp_bridge

    return _probe_mcp_bridge(mcp_bridge_url)


def environment_check_payload(
    request: Any,
    cfg: dict[str, Any],
    *,
    org_registry: Any | None = None,
) -> dict[str, Any]:
    """Return structured checks + fix hints so NL can proceed without back-and-forth."""
    checks: list[dict[str, Any]] = []
    fixes: list[dict[str, Any]] = []

    bridge_url = (cfg.get("mcp_bridge_url") or "").strip()
    probe = _probe_bridge(bridge_url) if bridge_url else {"reachable": False, "hint": "No URL configured"}
    bridge_ok = bool(probe.get("reachable"))
    llm_ok = bool(probe.get("llm_configured")) if bridge_ok else False

    if not bridge_url:
        bridge_detail = "No mcp_bridge_url on asset"
    elif not bridge_ok:
        bridge_detail = probe.get("hint") or probe.get("error") or "Unreachable from SOAR"
    elif llm_ok:
        model = probe.get("llm_model") or "configured"
        mode = probe.get("llm_mode") or "llm"
        bridge_detail = f"Online — LLM ready ({model}, {mode})"
    else:
        bridge_detail = (
            "Online — bridge reachable; LLM not configured (custom NL returns stubs/templates only)"
        )

    checks.append(
        {
            "id": "mcp_bridge",
            "severity": "ok" if bridge_ok else "warn",
            "title": "MCP bridge",
            "detail": bridge_detail,
        }
    )
    if bridge_ok:
        checks.append(
            {
                "id": "llm",
                "severity": "ok" if llm_ok else "warn",
                "title": "LLM / model API",
                "detail": (
                    f"Configured — {probe.get('llm_model') or 'model ready'}"
                    if llm_ok
                    else (probe.get("llm_hint") or "Set OPENAI_API_KEY or OPENAI_BASE_URL on MCP bridge host")
                ),
            }
        )
        if not llm_ok:
            fixes.append(
                {
                    "id": "configure_llm",
                    "label": "Configure LLM on MCP bridge",
                    "hint": probe.get("llm_hint")
                    or "OPENAI_API_KEY or OPENAI_BASE_URL + AGENT_BRIDGE_MODEL — see docs/ON_PREM_LLM.md",
                }
            )
    if not bridge_ok:
        fixes.append(
            {
                "id": "use_template",
                "label": "Use template instead",
                "action": "scaffold",
                "hint": "Works without MCP — pick Templates or Wizard",
            }
        )
        fixes.append(
            {
                "id": "retry_bridge",
                "label": "Retry bridge check",
                "action": "bridge_status",
            }
        )
        if bridge_url:
            fixes.append(
                {
                    "id": "fix_bridge_url",
                    "label": "Verify mcp_bridge_url on asset",
                    "hint": f"Current: {bridge_url}",
                }
            )

    defaults = parse_asset_defaults(cfg.get("asset_defaults"))
    suggested_defaults = discover_suggested_defaults(request)
    if defaults:
        checks.append(
            {
                "id": "asset_defaults",
                "severity": "ok",
                "title": "Asset defaults",
                "detail": ", ".join(f"{k}→{v}" for k, v in sorted(defaults.items())[:6]),
            }
        )
    else:
        checks.append(
            {
                "id": "asset_defaults",
                "severity": "info",
                "title": "Asset defaults",
                "detail": "Not set — integration preflight may ask for assets at import",
            }
        )
        fixes.append(
            {
                "id": "set_asset_defaults",
                "label": "Set asset_defaults on asset",
                "hint": 'JSON e.g. {"okta":"okta","slack":"slack_lab"}',
            }
        )
        if suggested_defaults:
            fixes.insert(
                0,
                {
                    "id": "apply_asset_defaults",
                    "label": "Fix environment (apply defaults)",
                    "action": "apply_environment_fixes",
                    "hint": ", ".join(
                        f"{k}→{v}" for k, v in sorted(suggested_defaults.items())[:6]
                    ),
                    "auto": True,
                },
            )

    demo_patterns = [p for p in RUNTIME_FIXTURES if RUNTIME_FIXTURES[p].tier == "safe"][:5]
    from case_catalog import DEFAULT_SAMPLE_CASES, sample_ids

    ids = sample_ids()
    id_range = f"{ids[0]}–{ids[-1]}" if len(ids) >= 2 else str(ids[0] if ids else "")
    checks.append(
        {
            "id": "demo_data",
            "severity": "ok",
            "title": "Demo cases",
            "detail": f"{len(demo_patterns)} safe fixtures + {len(DEFAULT_SAMPLE_CASES)} sample cases ({id_range})",
        }
    )
    fixes.append(
        {
            "id": "provision_demo",
            "label": "Create demo case on SOAR",
            "action": "provision_demo_case",
            "hint": "Sample case → real container with artifacts",
        }
    )

    patterns = list_patterns_payload(org_registry=org_registry)
    offline_count = len(patterns.get("patterns") or [])

    cap = index_status()
    if cap.get("loaded"):
        cap_detail = (
            f"{cap.get('app_count')} apps, {cap.get('action_count')} actions — "
            f"v{cap.get('index_version') or '?'}"
            + (" (stale)" if cap.get("stale") else "")
        )
        cap_severity = "warn" if cap.get("stale") else "ok"
    else:
        cap_detail = "Not built — run rebuild capability index (baseline only until then)"
        cap_severity = "info"
    checks.append(
        {
            "id": "capability_index",
            "severity": cap_severity,
            "title": "Capability index",
            "detail": cap_detail,
        }
    )
    if not cap.get("loaded") or cap.get("stale"):
        fixes.append(
            {
                "id": "rebuild_capability_index",
                "label": "Rebuild capability index",
                "action": "rebuild_capability_index",
                "hint": "Harvests local SOAR apps/actions — required for air-gap IR validation",
            }
        )

    nl_ready = (bridge_ok and llm_ok) or (not bridge_ok and offline_count > 0)
    if bridge_ok and llm_ok:
        nl_mode = "llm"
    elif bridge_ok:
        nl_mode = "bridge_stub"
    else:
        nl_mode = "offline_templates"

    checks.append(
        {
            "id": "ui_persona",
            "severity": "info",
            "title": "UI persona",
            "detail": (
                f"default_ui_mode={cfg.get('default_ui_mode') or 'studio'} — "
                "append ?mode=coach|assistant|tutor or use es_link / splunk_link drilldowns"
            ),
        }
    )

    blocking = sum(1 for c in checks if c.get("severity") == "error")

    cap_loaded = cap.get("loaded")
    setup_complete = bool(cap_loaded) and blocking == 0

    fixes.append(
        {
            "id": "export_asset_config",
            "label": "Export asset config",
            "action": "export_asset_config",
            "hint": "Save JSON before migrating to a new SOAR instance",
        }
    )
    fixes.append(
        {
            "id": "run_self_test",
            "label": "Run self-test",
            "action": "run_self_test",
            "hint": "Verify capability index, templates, and demo data",
        }
    )

    return {
        "status": "success",
        "nl_ready": nl_ready,
        "nl_mode": nl_mode,
        "bridge_reachable": bridge_ok,
        "llm_configured": llm_ok,
        "llm_mode": probe.get("llm_mode") if bridge_ok else None,
        "llm_model": probe.get("llm_model") if bridge_ok else None,
        "checks": checks,
        "fixes": fixes,
        "blocking_count": blocking,
        "setup_complete": setup_complete,
        "capability_index_loaded": bool(cap_loaded),
        "message": (
            "Natural language ready — MCP bridge and LLM configured."
            if bridge_ok and llm_ok
            else (
                "MCP bridge online but LLM not configured — templates/stubs only for custom NL; "
                "set OPENAI_API_KEY or OPENAI_BASE_URL on the bridge host."
                if bridge_ok
                else "MCP offline — use Templates/Wizard or fix bridge; offline keyword build still works."
            )
        ),
        "demo_sample_ids": sample_ids(),
        "showcase_sample_ids": [
            int(row["id"]) for row in DEFAULT_SAMPLE_CASES if row.get("showcase_recommended")
        ],
        "suggested_asset_defaults": suggested_defaults,
    }
