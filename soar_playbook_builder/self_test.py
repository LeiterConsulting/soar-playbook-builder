"""Post-install self-test — capability index, templates, demo data, optional bridge."""

from __future__ import annotations

from typing import Any, Callable

from builder_helpers import SCAFFOLDS, analyze_playbook
from capability.index import index_status, load_baseline_apps
from case_catalog import sample_ids
from compiler import compile_playbook, parse_python_ir, parse_visual_ir
from ir.fixtures import smoke_ir_document
from ir.schema import PlaybookIR
from retrieve import TemplateLibrary
from trusted_review import ReviewContext, review_template
from validate import preflight
from validate.fixtures import (
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
    qualified_smoke_ir,
)


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

    insecure_bridge = str(
        cfg.get("mcp_bridge_allow_insecure_http") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    insecure_loopback = str(
        cfg.get("soar_loopback_allow_insecure_tls") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    secure_transport = not insecure_bridge and not insecure_loopback
    _check(
        checks,
        check_id="transport_security",
        title="Transport security",
        ok=secure_transport,
        detail=(
            "TLS verification and HTTPS policy enabled"
            if secure_transport
            else "Lab-only insecure transport override is enabled"
        ),
        severity="warn",
    )

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

    try:
        compiler_ir = PlaybookIR.from_dict(smoke_ir_document())
        artifacts = compile_playbook(compiler_ir)
        compiler_ok = (
            parse_python_ir(artifacts.python_source).sha256() == compiler_ir.sha256()
            and parse_visual_ir(artifacts.visual).sha256() == compiler_ir.sha256()
        )
        compiler_detail = (
            f"Dual artifact round-trip {compiler_ir.sha256()[:12]}"
            if compiler_ok
            else "Compiler artifact hash mismatch"
        )
    except (KeyError, TypeError, ValueError) as exc:
        compiler_ok = False
        compiler_detail = f"Compiler self-test failed: {type(exc).__name__}"
    _check(
        checks,
        check_id="deterministic_compiler",
        title="Deterministic compiler",
        ok=compiler_ok,
        detail=compiler_detail,
    )

    try:
        clean_report = preflight(
            qualified_smoke_ir(),
            qualified_smoke_index(),
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
        bad_document = qualified_smoke_document()
        bad_action = next(
            node for node in bad_document["nodes"] if node["type"] == "action"
        )
        bad_action["asset"] = {"kind": "asset_unbound"}
        bad_report = preflight(
            PlaybookIR.from_dict(bad_document),
            qualified_smoke_index(),
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
        validator_ok = (
            clean_report.status == "ok"
            and bad_report.status == "blocked"
            and any(gap.id == "ASSET_UNBOUND" for gap in bad_report.gaps)
        )
        validator_detail = (
            "Known-good accepted; known-bad asset blocked"
            if validator_ok
            else "Validator fixture outcome mismatch"
        )
    except (KeyError, TypeError, ValueError) as exc:
        validator_ok = False
        validator_detail = f"Validator self-test failed: {type(exc).__name__}"
    _check(
        checks,
        check_id="deterministic_preflight",
        title="Deterministic preflight",
        ok=validator_ok,
        detail=validator_detail,
    )

    try:
        library = TemplateLibrary.load()
        template_records = library.records
        template_roundtrips = all(
            parse_python_ir(
                compile_playbook(record.ir).python_source
            ).sha256()
            == record.ir.sha256()
            and parse_visual_ir(
                compile_playbook(record.ir).visual
            ).sha256()
            == record.ir.sha256()
            for record in template_records
        )
        templates_ok = len(template_records) == 11 and template_roundtrips
        templates_detail = (
            "11 canonical IR templates parsed and dual-compiled"
            if templates_ok
            else "Canonical IR template count or round-trip mismatch"
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        templates_ok = False
        templates_detail = (
            f"Canonical template self-test failed: {type(exc).__name__}"
        )
    _check(
        checks,
        check_id="canonical_ir_templates",
        title="Canonical IR templates",
        ok=templates_ok,
        detail=templates_detail,
    )

    try:
        review = review_template(
            "hello",
            qualified_smoke_index(),
            context=ReviewContext(
                operating_mode="air_gapped",
                evaluated_at=FIXTURE_EVALUATED_AT,
                generated_at=FIXTURE_EVALUATED_AT,
                origin="template",
            ),
        )
        review_lock_ok = (
            review.get("status") == "success"
            and review.get("review_only") is True
            and review.get("import_enabled") is False
            and review.get("ready_for_import") is False
            and review.get("import_block_reason")
            == "TRUSTED_IMPORT_DISABLED"
        )
        review_lock_detail = (
            "Hello reviewed; trusted Import remains locked"
            if review_lock_ok
            else "Trusted review lock invariant failed"
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        review_lock_ok = False
        review_lock_detail = (
            f"Trusted review self-test failed: {type(exc).__name__}"
        )
    _check(
        checks,
        check_id="trusted_review_lock",
        title="Trusted review safety lock",
        ok=review_lock_ok,
        detail=review_lock_detail,
    )

    from custom_templates import parse_org_templates

    org_registry = parse_org_templates(
        cfg.get("custom_templates_json"),
        raw_ir_config=cfg.get("custom_ir_templates_json"),
        allow_legacy_python=str(
            cfg.get("allow_legacy_python_templates") or ""
        ).strip().lower()
        in {"1", "true", "yes", "on"},
    )
    org_templates_ok = not org_registry.errors
    org_detail = (
        f"{org_registry.count} strict/explicit organization templates loaded"
        if org_templates_ok and not org_registry.warnings
        else "; ".join(
            [*org_registry.errors[:2], *org_registry.warnings[:2]]
        )
        or "Organization template configuration is valid"
    )
    _check(
        checks,
        check_id="organization_templates",
        title="Organization template boundary",
        ok=org_templates_ok and not org_registry.warnings,
        detail=org_detail,
        severity="warn",
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
