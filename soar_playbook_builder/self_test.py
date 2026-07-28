"""Post-install self-test — capability index, templates, demo data, optional bridge."""

from __future__ import annotations

from typing import Any, Callable

from builder_helpers import SCAFFOLDS, analyze_playbook
from capability.index import index_status, load_baseline_apps
from case_catalog import sample_ids


def _check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    title: str,
    ok: bool,
    detail: str,
    severity: str = "error",
) -> None:
    checks.append(
        {
            "id": check_id,
            "title": title,
            "status": "ok" if ok else severity,
            "detail": detail,
        }
    )


def run_self_test(
    cfg: dict[str, Any],
    *,
    bridge_probe: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run offline-safe checks; optional bridge_probe for MCP health."""
    checks: list[dict[str, Any]] = []

    cap = index_status()
    cap_ok = bool(cap.get("loaded")) and int(cap.get("app_count") or 0) >= 3
    _check(
        checks,
        check_id="capability_index",
        title="Capability index",
        ok=cap_ok,
        detail=(
            f"{cap.get('app_count')} apps, {cap.get('action_count')} actions"
            if cap_ok
            else (cap.get("harvest_errors") or ["Run rebuild capability index"])[0]
            if isinstance(cap.get("harvest_errors"), list)
            else "Run rebuild capability index on the asset"
        ),
        severity="warn" if cap.get("baseline_only") else "error",
    )

    baseline = load_baseline_apps()
    _check(
        checks,
        check_id="baseline_catalog",
        title="Baseline app catalog",
        ok=len(baseline) >= 3,
        detail=f"{len(baseline)} baseline apps shipped",
    )

    hello = SCAFFOLDS.get("hello") or ""
    hello_ok = bool(hello) and analyze_playbook(hello).get("valid_python") is not False
    _check(
        checks,
        check_id="hello_template",
        title="Hello template scaffold",
        ok=hello_ok,
        detail="Python validates" if hello_ok else "Hello scaffold missing or invalid",
    )

    ids = sample_ids()
    demo_ok = len(ids) >= 5 and ids[0] == 9001
    _check(
        checks,
        check_id="demo_samples",
        title="Demo sample cases",
        ok=demo_ok,
        detail=f"Built-in samples {ids[0]}–{ids[-1]}" if demo_ok else f"Unexpected sample ids: {ids}",
    )

    defaults = (cfg.get("asset_defaults") or "").strip()
    _check(
        checks,
        check_id="asset_defaults",
        title="Asset defaults",
        ok=bool(defaults),
        detail="Configured" if defaults else "Optional — set for smoother import preflight",
        severity="info" if not defaults else "ok",
    )

    bridge_url = (cfg.get("mcp_bridge_url") or "").strip()
    if bridge_url and bridge_probe:
        probe = bridge_probe()
        reachable = bool(probe.get("reachable"))
        llm = bool(probe.get("llm_configured")) if reachable else False
        _check(
            checks,
            check_id="mcp_bridge",
            title="MCP bridge",
            ok=reachable,
            detail=probe.get("hint") or probe.get("error") or ("Online" if reachable else "Unreachable"),
            severity="warn",
        )
        if reachable:
            _check(
                checks,
                check_id="llm",
                title="LLM / model API",
                ok=llm,
                detail=(
                    f"Configured — {probe.get('llm_model') or 'model ready'}"
                    if llm
                    else probe.get("llm_hint") or "Bridge online but LLM not configured"
                ),
                severity="info" if not llm else "ok",
            )
    elif bridge_url:
        _check(
            checks,
            check_id="mcp_bridge",
            title="MCP bridge",
            ok=True,
            detail="URL configured — run test connectivity from asset for live probe",
            severity="info",
        )

    blocking = sum(1 for c in checks if c.get("status") not in ("ok", "info"))
    passed = sum(1 for c in checks if c.get("status") == "ok")
    return {
        "status": "success" if blocking == 0 else "needs_attention",
        "passed": passed,
        "blocking": blocking,
        "check_count": len(checks),
        "checks": checks,
        "message": (
            f"Self-test passed ({passed}/{len(checks)} checks ok)."
            if blocking == 0
            else f"Self-test: {blocking} item(s) need attention."
        ),
        "setup_complete": blocking == 0 and cap_ok,
    }
