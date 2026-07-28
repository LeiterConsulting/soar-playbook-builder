#!/usr/bin/env python3
"""
End-to-end validation for SOAR Playbook Builder (production app).

Runs automated checks against SOAR REST + sidecar handler APIs, optional MCP bridge,
and emits JSON + Markdown + HTML reports with quick-verify URLs.

Usage:
  SOAR_URL=... SOAR_USER=... SOAR_PASSWORD=... python scripts/e2e_validate.py
  python scripts/e2e_validate.py --mode A --skip-import
  python scripts/e2e_validate.py --report-dir dist/e2e

Requires: httpx (pip install httpx)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import quote

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx", file=sys.stderr)
    sys.exit(2)

Status = Literal["ok", "warn", "error", "skipped", "manual"]

PLAYBOOK_BUILDER_APPID = "a7c3e891-4f2d-4b18-9e6a-1d5f8c2b0e47"
_SOURCE_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "soar_playbook_builder"
    / "soar_playbook_builder.json"
)
try:
    _SOURCE_VERSION_TEXT = str(
        json.loads(_SOURCE_MANIFEST.read_text(encoding="utf-8"))[
            "app_version"
        ]
    )
    MIN_APP_VERSION = tuple(
        int(part) for part in _SOURCE_VERSION_TEXT.split(".")
    )
except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
    MIN_APP_VERSION = (2, 26, 0)
E2E_PLAYBOOK_PREFIX = "PB_E2E_"

PHASE_IDS = (
    "1-prerequisites",
    "2-soar-platform",
    "3-sidecar-api",
    "4-import",
    "5-mcp-bridge",
    "6-manual-signoff",
)

OnCheckCallback = Callable[[dict[str, Any]], None]


@dataclass
class E2ECheck:
    id: str
    phase: str
    title: str
    status: Status
    message: str
    automated: bool = True
    verify_url: str | None = None
    manual_verify: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class E2EContext:
    soar_url: str
    soar_user: str
    soar_password: str
    verify_ssl: bool
    asset_name: str
    mcp_bridge_url: str
    mode: str  # A, B, or auto
    skip_import: bool
    cleanup_import: bool
    directory: str = ""
    app_version: str = ""
    sidecar_base: str = ""
    imported_playbook_id: str = ""
    imported_playbook_name: str = ""
    hello_source: str = ""


def _parse_version(ver: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", ver)[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def _status_icon(s: Status) -> str:
    return {"ok": "✓", "warn": "!", "error": "✗", "skipped": "–", "manual": "◎"}.get(s, "?")


def _soar_client(ctx: E2EContext, timeout: float = 45.0) -> httpx.Client:
    return httpx.Client(
        base_url=ctx.soar_url.rstrip("/"),
        auth=(ctx.soar_user, ctx.soar_password),
        verify=ctx.verify_ssl,
        timeout=timeout,
        headers={"Accept": "application/json"},
        trust_env=False,
    )


def _handler_chat_url(ctx: E2EContext, query: str = "") -> str:
    base = f"{ctx.soar_url.rstrip('/')}/rest/handler/{ctx.directory}/{ctx.asset_name}/chat"
    return f"{base}?{query}" if query else base


def _soar_ui_links(ctx: E2EContext) -> dict[str, str]:
    base = ctx.soar_url.rstrip("/")
    return {
        "soar_home": f"{base}/",
        "soar_apps": f"{base}/mission/#/apps",
        "soar_playbooks": f"{base}/mission/#/playbooks",
        "soar_app_rest": f"{base}/rest/app",
        "sidecar": _handler_chat_url(ctx),
        "sidecar_hello_scaffold": f"{_handler_chat_url(ctx)}#/build",
        "sidecar_validate": f"{_handler_chat_url(ctx)}#/build",
        "sidecar_bridge_status": _handler_chat_url(ctx, "action=bridge_status"),
        "mcp_health": _mcp_health_url(ctx.mcp_bridge_url),
    }


def _mcp_health_url(bridge: str) -> str:
    b = bridge.rstrip("/")
    if not b:
        return ""
    if b.endswith("/agent"):
        return b.rsplit("/agent", 1)[0] + "/agent/health"
    return f"{b}/health"


class LiveCheckList(list):
    """Appends E2ECheck items and invokes optional live callback."""

    def __init__(self, on_check: OnCheckCallback | None = None) -> None:
        super().__init__()
        self._on_check = on_check

    def append(self, item: E2ECheck) -> None:  # type: ignore[override]
        super().append(item)
        if self._on_check:
            self._on_check(item.to_dict())


def _add(checks: list[E2ECheck], check: E2ECheck) -> None:
    checks.append(check)


def _run_phase_config(ctx: E2EContext, checks: list[E2ECheck]) -> None:
    issues: list[str] = []
    if not (ctx.soar_url or "").strip():
        issues.append("SOAR_URL")
    elif "your-soar.example.com" in ctx.soar_url:
        issues.append("SOAR_URL (still placeholder — edit scripts/env.e2e.local)")
    if not (ctx.soar_user or "").strip():
        issues.append("SOAR_USER")
    if not (ctx.soar_password or "").strip() or ctx.soar_password.strip() == "change-me":
        issues.append("SOAR_PASSWORD")
    if issues:
        _add(checks, E2ECheck(
            id="env_required",
            phase="1-prerequisites",
            title="Required environment variables",
            status="error",
            message=f"Missing: {', '.join(issues)}",
            verify_url=None,
            manual_verify="Set SOAR_URL, SOAR_USER, SOAR_PASSWORD in scripts/env.e2e.local (or sidecar-ui/.env.local)",
        ))
    else:
        _add(checks, E2ECheck(
            id="env_required",
            phase="1-prerequisites",
            title="Required environment variables",
            status="ok",
            message=f"SOAR_URL={ctx.soar_url}, asset={ctx.asset_name}, mode={ctx.mode}",
        ))


def _run_phase_soar(ctx: E2EContext, checks: list[E2ECheck], client: httpx.Client) -> bool:
    links = _soar_ui_links(ctx)
    ok = True

    try:
        r = client.get("/rest/version")
        if r.status_code == 200:
            _add(checks, E2ECheck(
                id="soar_rest",
                phase="2-soar-platform",
                title="SOAR REST API reachable",
                status="ok",
                message=f"HTTP {r.status_code}",
                verify_url=links["soar_home"],
                manual_verify="Open SOAR home — login succeeds with same credentials.",
            ))
        else:
            ok = False
            _add(checks, E2ECheck(
                id="soar_rest",
                phase="2-soar-platform",
                title="SOAR REST API reachable",
                status="error",
                message=f"HTTP {r.status_code}: {r.text[:200]}",
                verify_url=links["soar_home"],
            ))
    except Exception as exc:
        ok = False
        _add(checks, E2ECheck(
            id="soar_rest",
            phase="2-soar-platform",
            title="SOAR REST API reachable",
            status="error",
            message=str(exc),
            verify_url=links["soar_home"],
        ))
        return False

    app_row: dict[str, Any] | None = None
    try:
        r = client.get("/rest/app", params={"_page_size": 200})
        r.raise_for_status()
        data = r.json()
        apps = data.get("data") if isinstance(data, dict) else data
        for app in apps or []:
            if not isinstance(app, dict):
                continue
            if app.get("appid") == PLAYBOOK_BUILDER_APPID:
                app_row = app
                break
            n = (app.get("name") or "").lower()
            pkg = (app.get("package_name") or "").lower()
            if pkg in ("soar_playbook_builder", "phantom_playbook_builder") or (
                "playbook" in n and "builder" in n
            ):
                app_row = app

        if not app_row:
            ok = False
            _add(checks, E2ECheck(
                id="app_installed",
                phase="2-soar-platform",
                title="Playbook Builder app installed",
                status="error",
                message="App not found in /rest/app",
                verify_url=links["soar_apps"],
                manual_verify="Apps → Install App → soar_playbook_builder.tgz",
            ))
        else:
            ctx.directory = str(app_row.get("directory") or "")
            ctx.app_version = str(app_row.get("app_version") or "0")
            ctx.sidecar_base = (
                f"{ctx.soar_url.rstrip('/')}/rest/handler/{ctx.directory}/{ctx.asset_name}"
            )
            links = _soar_ui_links(ctx)

            _add(checks, E2ECheck(
                id="app_installed",
                phase="2-soar-platform",
                title="Playbook Builder app installed",
                status="ok",
                message=f"{app_row.get('name')} v{ctx.app_version}",
                verify_url=links["soar_apps"],
                manual_verify="Apps list shows SOAR Playbook Builder enabled.",
                detail={"directory": ctx.directory, "appid": app_row.get("appid")},
            ))

            ver_ok = _parse_version(ctx.app_version) >= MIN_APP_VERSION
            _add(checks, E2ECheck(
                id="app_version",
                phase="2-soar-platform",
                title="App version meets minimum",
                status="ok" if ver_ok else "warn",
                message=f"v{ctx.app_version} (minimum {'.'.join(map(str, MIN_APP_VERSION))})",
                verify_url=links["soar_app_rest"],
            ))
            if not ver_ok:
                ok = False

            if not ctx.directory:
                ok = False
                _add(checks, E2ECheck(
                    id="handler_directory",
                    phase="2-soar-platform",
                    title="REST handler directory registered",
                    status="error",
                    message="directory field empty — reinstall app",
                    verify_url=links["soar_apps"],
                ))
    except Exception as exc:
        ok = False
        _add(checks, E2ECheck(
            id="app_installed",
            phase="2-soar-platform",
            title="Playbook Builder app installed",
            status="error",
            message=str(exc),
            verify_url=links["soar_apps"],
        ))
        return ok

    # Asset lookup
    try:
        r = client.get("/rest/asset", params={"_page_size": 200})
        r.raise_for_status()
        assets = r.json().get("data") if isinstance(r.json(), dict) else []
        found = None
        for a in assets or []:
            if not isinstance(a, dict):
                continue
            if (a.get("name") or "").lower() == ctx.asset_name.lower():
                found = a
                break
        if not found:
            ok = False
            _add(checks, E2ECheck(
                id="asset_exists",
                phase="2-soar-platform",
                title=f"Asset '{ctx.asset_name}' exists",
                status="error",
                message="Create asset under SOAR Playbook Builder app",
                verify_url=links["soar_apps"],
                manual_verify=f"Apps → SOAR Playbook Builder → Create Asset → name `{ctx.asset_name}`",
            ))
        else:
            asset_id = found.get("id")
            asset_ui = f"{ctx.soar_url.rstrip('/')}/mission/#/asset/{asset_id}"
            bridge = ""
            try:
                cfg = found.get("configuration") or {}
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                bridge = str(cfg.get("mcp_bridge_url") or "")
            except Exception:  # noqa: BLE001
                pass
            _add(checks, E2ECheck(
                id="asset_exists",
                phase="2-soar-platform",
                title=f"Asset '{ctx.asset_name}' exists",
                status="ok",
                message=f"Asset id={asset_id}, mcp_bridge_url={bridge or '(default)'}",
                verify_url=asset_ui,
                manual_verify="Open asset — confirm mcp_bridge_url for Mode B.",
                detail={"asset_id": asset_id, "mcp_bridge_url": bridge},
            ))
    except Exception as exc:
        ok = False
        _add(checks, E2ECheck(
            id="asset_exists",
            phase="2-soar-platform",
            title=f"Asset '{ctx.asset_name}' exists",
            status="error",
            message=str(exc),
        ))

    return ok


def _handler_get(ctx: E2EContext, client: httpx.Client, query: str) -> tuple[dict[str, Any] | None, str | None]:
    url = _handler_chat_url(ctx, query)
    try:
        r = client.get(url, headers={"Accept": "application/json, text/html"})
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        ct = r.headers.get("content-type", "")
        if "json" in ct or r.text.strip().startswith("{"):
            return r.json(), None
        return {"_html": r.text[:500], "_status": r.status_code}, None
    except Exception as exc:
        return None, str(exc)


def _handler_post(ctx: E2EContext, client: httpx.Client, body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    url = _handler_chat_url(ctx)
    try:
        r = client.post(
            url,
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120.0,
        )
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def _run_phase_sidecar(ctx: E2EContext, checks: list[E2ECheck], client: httpx.Client) -> bool:
    if not ctx.directory:
        _add(checks, E2ECheck(
            id="sidecar_skip",
            phase="3-sidecar-api",
            title="Sidecar API checks",
            status="skipped",
            message="No handler directory — prior step failed",
        ))
        return False

    links = _soar_ui_links(ctx)
    ok = True

    data, err = _handler_get(ctx, client, "")
    if err:
        ok = False
        _add(checks, E2ECheck(
            id="sidecar_html",
            phase="3-sidecar-api",
            title="Sidecar page loads",
            status="error",
            message=err,
            verify_url=links["sidecar"],
        ))
    else:
        html = (data or {}).get("_html") or ""
        has_ui = "playbook_builder" in html.lower() or "playbook builder" in html.lower()
        _add(checks, E2ECheck(
            id="sidecar_html",
            phase="3-sidecar-api",
            title="Sidecar page loads",
            status="ok" if has_ui or html else "warn",
            message="HTML response received" if html else "JSON-only response (unexpected for GET /chat)",
            verify_url=links["sidecar"],
            manual_verify="Browser: sidecar shows Playbook Builder header and preview panels.",
        ))

    data, err = _handler_post(
        ctx,
        client,
        {"action": "scaffold", "pattern": "hello"},
    )
    if err:
        ok = False
        _add(checks, E2ECheck(
            id="scaffold_hello",
            phase="3-sidecar-api",
            title="Hello World scaffold (Mode A core)",
            status="error",
            message=err,
            verify_url=links["sidecar_hello_scaffold"],
        ))
    else:
        src = (data or {}).get("source") or ""
        ctx.hello_source = src
        _add(checks, E2ECheck(
            id="scaffold_hello",
            phase="3-sidecar-api",
            title="Hello World scaffold (Mode A core)",
            status="ok" if src else "error",
            message=f"{len(src)} bytes Python source" if src else "No source in response",
            verify_url=links["sidecar_hello_scaffold"],
            manual_verify="Open link — JSON with source and preview arrays.",
            detail={"pattern": (data or {}).get("pattern")},
        ))
        if not src:
            ok = False

    data, err = _handler_post(
        ctx,
        client,
        {"action": "validate", "pattern": "hello"},
    )
    if err:
        ok = False
        _add(checks, E2ECheck(
            id="validate_hello",
            phase="3-sidecar-api",
            title="Hello World validation",
            status="error",
            message=err,
            verify_url=links["sidecar_validate"],
        ))
    else:
        analysis = (data or {}).get("analysis") or {}
        score = analysis.get("score") if isinstance(analysis, dict) else None
        st: Status = "ok"
        if score is not None and isinstance(score, (int, float)) and score < 60:
            st = "warn"
        _add(checks, E2ECheck(
            id="validate_hello",
            phase="3-sidecar-api",
            title="Hello World validation",
            status=st if data else "error",
            message=f"score={score}" if score is not None else "validation payload OK",
            verify_url=links["sidecar_validate"],
        ))

    data, err = _handler_get(ctx, client, "action=steps")
    _add(checks, E2ECheck(
        id="builder_steps",
        phase="3-sidecar-api",
        title="Builder steps API",
        status="ok" if data and not err else "warn",
        message=err or f"{len((data or {}).get('steps') or [])} steps returned",
        verify_url=_handler_chat_url(ctx, "action=steps"),
    ))

    return ok


def _run_phase_bridge(ctx: E2EContext, checks: list[E2ECheck], client: httpx.Client) -> None:
    links = _soar_ui_links(ctx)
    want_bridge = ctx.mode in ("B", "auto")

    data, err = _handler_get(ctx, client, "action=bridge_status")
    reachable = bool((data or {}).get("reachable")) if data else False

    if ctx.mode == "A":
        _add(checks, E2ECheck(
            id="bridge_status_soar",
            phase="5-mcp-bridge",
            title="MCP bridge status from SOAR (Mode A)",
            status="skipped",
            message="Mode A — bridge not required",
        ))
    else:
        st: Status = "ok" if reachable else ("warn" if ctx.mode == "auto" else "error")
        _add(checks, E2ECheck(
            id="bridge_status_soar",
            phase="5-mcp-bridge",
            title="MCP bridge reachable from SOAR server",
            status=st,
            message=(data or {}).get("error") or ("reachable" if reachable else "not reachable"),
            verify_url=links["sidecar_bridge_status"],
            manual_verify="Sidecar status pill should show AI connected when Mode B.",
            detail=data or {},
        ))

    if not ctx.mcp_bridge_url or ctx.mode == "A":
        _add(checks, E2ECheck(
            id="mcp_health_runner",
            phase="5-mcp-bridge",
            title="MCP health from validation runner",
            status="skipped",
            message="MCP_BRIDGE_URL not set or Mode A",
        ))
        return

    health = _mcp_health_url(ctx.mcp_bridge_url)
    try:
        with httpx.Client(verify=ctx.verify_ssl, timeout=12.0, trust_env=False) as hc:
            r = hc.get(health)
        st = "ok" if r.status_code == 200 else "warn"
        _add(checks, E2ECheck(
            id="mcp_health_runner",
            phase="5-mcp-bridge",
            title="MCP health from validation runner",
            status=st,
            message=f"HTTP {r.status_code} at {health}",
            verify_url=health,
            manual_verify="Also verify from SOAR server shell: curl same URL.",
        ))
    except Exception as exc:
        _add(checks, E2ECheck(
            id="mcp_health_runner",
            phase="5-mcp-bridge",
            title="MCP health from validation runner",
            status="warn" if ctx.mode == "auto" else "error",
            message=str(exc),
            verify_url=health,
        ))

    if want_bridge and ctx.mode == "B":
        nl_msg = quote("Build a minimal hello world playbook that adds a note to the container")
        data, err = _handler_get(ctx, client, f"message={nl_msg}")
        if err:
            _add(checks, E2ECheck(
                id="nl_chat_proxy",
                phase="5-mcp-bridge",
                title="NL chat via MCP proxy",
                status="error",
                message=err,
                verify_url=links["sidecar"],
            ))
        else:
            has = bool((data or {}).get("source") or (data or {}).get("preview"))
            _add(checks, E2ECheck(
                id="nl_chat_proxy",
                phase="5-mcp-bridge",
                title="NL chat via MCP proxy",
                status="ok" if has else "warn",
                message="Preview/source returned" if has else "Empty NL response",
                verify_url=links["sidecar"],
                manual_verify="Type a NL prompt in sidecar chat — preview updates.",
            ))


def _run_phase_import(ctx: E2EContext, checks: list[E2ECheck], client: httpx.Client) -> None:
    links = _soar_ui_links(ctx)
    if ctx.skip_import:
        _add(checks, E2ECheck(
            id="import_hello",
            phase="4-import",
            title="Import Hello World playbook",
            status="skipped",
            message="--skip-import",
        ))
        return

    if not ctx.hello_source:
        _add(checks, E2ECheck(
            id="import_hello",
            phase="4-import",
            title="Import Hello World playbook",
            status="error",
            message="No hello source from scaffold step",
        ))
        return

    ts = int(time.time())
    name = f"{E2E_PLAYBOOK_PREFIX}Hello_{ts}"
    body = {
        "action": "import_draft",
        "confirm": True,
        "source": ctx.hello_source,
        "name": name,
        "pattern": "hello",
    }
    data, err = _handler_post(ctx, client, body)
    if err:
        _add(checks, E2ECheck(
            id="import_hello",
            phase="4-import",
            title="Import Hello World playbook",
            status="error",
            message=err,
            verify_url=links["sidecar"],
        ))
        return

    st = (data or {}).get("status")
    pb_id = str((data or {}).get("playbook_id") or "")
    if st == "success" and pb_id:
        ctx.imported_playbook_id = pb_id
        ctx.imported_playbook_name = str((data or {}).get("playbook_name") or name)
        vpe = f"{ctx.soar_url.rstrip('/')}/playbook/{pb_id}?editor=visual"
        _add(checks, E2ECheck(
            id="import_hello",
            phase="4-import",
            title="Import Hello World playbook",
            status="ok",
            message=f"Imported id={pb_id} name={ctx.imported_playbook_name}",
            verify_url=vpe,
            manual_verify="Open Visual Editor — blocks match Hello scaffold.",
            detail={"playbook_id": pb_id, "playbook_name": ctx.imported_playbook_name},
        ))
    else:
        _add(checks, E2ECheck(
            id="import_hello",
            phase="4-import",
            title="Import Hello World playbook",
            status="error",
            message=(data or {}).get("error") or f"status={st}",
            verify_url=links["soar_playbooks"],
        ))
        return

    # Confirm in REST
    try:
        r = client.get(f"/rest/playbook/{pb_id}")
        if r.status_code == 200:
            _add(checks, E2ECheck(
                id="playbook_rest",
                phase="4-import",
                title="Imported playbook visible in REST",
                status="ok",
                message=f"/rest/playbook/{pb_id} OK",
                verify_url=f"{ctx.soar_url.rstrip('/')}/rest/playbook/{pb_id}",
            ))
        else:
            _add(checks, E2ECheck(
                id="playbook_rest",
                phase="4-import",
                title="Imported playbook visible in REST",
                status="warn",
                message=f"HTTP {r.status_code}",
                verify_url=links["soar_playbooks"],
            ))
    except Exception as exc:
        _add(checks, E2ECheck(
            id="playbook_rest",
            phase="4-import",
            title="Imported playbook visible in REST",
            status="warn",
            message=str(exc),
        ))

    if ctx.cleanup_import and pb_id:
        try:
            client.delete(f"/rest/playbook/{pb_id}")
            _add(checks, E2ECheck(
                id="import_cleanup",
                phase="4-import",
                title="Cleanup E2E playbook",
                status="ok",
                message=f"Deleted playbook {pb_id}",
            ))
        except Exception as exc:
            _add(checks, E2ECheck(
                id="import_cleanup",
                phase="4-import",
                title="Cleanup E2E playbook",
                status="warn",
                message=f"Could not delete {pb_id}: {exc}",
                manual_verify=f"Delete playbook `{ctx.imported_playbook_name}` manually in Playbooks UI.",
            ))


def _run_phase_manual(ctx: E2EContext, checks: list[E2ECheck]) -> None:
    links = _soar_ui_links(ctx)
    manual = [
        ("manual_sidecar_ui", "Sidecar UI visual check", links["sidecar"],
         "Blocks + Code tabs render; Generate template works; no console errors."),
        ("manual_test_connectivity", "Test connectivity action", links["soar_apps"],
         f"Asset `{ctx.asset_name}` → Run **test connectivity** — success with sidecar URL."),
        ("manual_vpe", "Visual Editor open", links["soar_playbooks"],
         "After import, Open in SOAR opens the correct playbook (not a stale URL param)."),
    ]
    if ctx.imported_playbook_id and not ctx.cleanup_import:
        manual.append((
            "manual_imported_pb",
            "Review imported E2E playbook",
            f"{ctx.soar_url.rstrip('/')}/playbook/{ctx.imported_playbook_id}?editor=visual",
            f"Delete `{ctx.imported_playbook_name}` when review complete.",
        ))
    for cid, title, url, steps in manual:
        _add(checks, E2ECheck(
            id=cid,
            phase="6-manual-signoff",
            title=title,
            status="manual",
            message="Human verification required before GitHub release",
            automated=False,
            verify_url=url,
            manual_verify=steps,
        ))


def run_e2e(
    ctx: E2EContext,
    *,
    on_check: OnCheckCallback | None = None,
    phases: set[str] | None = None,
) -> dict[str, Any]:
    def _run(phase: str) -> bool:
        return phases is None or phase in phases

    checks: LiveCheckList = LiveCheckList(on_check)
    oc = on_check

    if _run("1-prerequisites"):
        _run_phase_config(ctx, checks)

    soar_ok = False
    if _run("2-soar-platform") or _run("3-sidecar-api") or _run("4-import") or _run("5-mcp-bridge"):
        with _soar_client(ctx) as client:
            if _run("2-soar-platform"):
                soar_ok = _run_phase_soar(ctx, checks, client)
            elif ctx.directory:
                soar_ok = True
            else:
                _run_phase_soar(ctx, checks, client)
                soar_ok = bool(ctx.directory)

            if soar_ok or ctx.directory:
                if _run("3-sidecar-api"):
                    _run_phase_sidecar(ctx, checks, client)
                if _run("4-import"):
                    _run_phase_import(ctx, checks, client)
                if _run("5-mcp-bridge"):
                    _run_phase_bridge(ctx, checks, client)

    if _run("6-manual-signoff"):
        _run_phase_manual(ctx, checks)

    summary = {"ok": 0, "warn": 0, "error": 0, "manual": 0, "skipped": 0}
    for c in checks:
        summary[c.status] = summary.get(c.status, 0) + 1

    overall: Status = "ok"
    if summary["error"]:
        overall = "error"  # type: ignore[assignment]
    elif summary["warn"]:
        overall = "warn"  # type: ignore[assignment]

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": ctx.mode,
        "summary": summary,
        "links": _soar_ui_links(ctx) if ctx.directory else {},
        "context": {
            "directory": ctx.directory,
            "app_version": ctx.app_version,
            "imported_playbook_id": ctx.imported_playbook_id,
        },
        "checks": [c.to_dict() for c in checks],
    }


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Playbook Builder E2E validation report",
        "",
        f"**Overall:** {report['status']}  ",
        f"**Time (UTC):** {report['timestamp']}  ",
        f"**Mode:** {report['mode']}  ",
        "",
        f"ok={report['summary']['ok']} warn={report['summary']['warn']} "
        f"error={report['summary']['error']} manual={report['summary']['manual']} skipped={report['summary']['skipped']}",
        "",
        "## Quick links",
        "",
    ]
    for k, url in (report.get("links") or {}).items():
        lines.append(f"- **{k}:** {url}")
    lines.extend(["", "## Checks by phase", ""])
    phase = ""
    for c in report["checks"]:
        if c["phase"] != phase:
            phase = c["phase"]
            lines.append(f"### {phase}")
            lines.append("")
        icon = _status_icon(c["status"])
        lines.append(f"- {icon} **{c['title']}** — {c['message']}")
        if c.get("verify_url"):
            lines.append(f"  - Verify: {c['verify_url']}")
        if c.get("manual_verify"):
            lines.append(f"  - Manual: {c['manual_verify']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(report: dict[str, Any], path: Path) -> None:
    rows = []
    for c in report["checks"]:
        url = c.get("verify_url") or ""
        link = f'<a href="{escape(url)}" target="_blank" rel="noopener">Open</a>' if url else ""
        manual = escape(c.get("manual_verify") or "")
        rows.append(
            f"<tr class='status-{c['status']}'>"
            f"<td>{escape(_status_icon(c['status']))}</td>"
            f"<td>{escape(c['phase'])}</td>"
            f"<td><strong>{escape(c['title'])}</strong>"
            f"<div class='msg'>{escape(c['message'])}</div>"
            f"<div class='manual'>{manual}</div></td>"
            f"<td>{link}</td>"
            f"<td>{'auto' if c.get('automated', True) else 'manual'}</td>"
            f"</tr>"
        )
    quick = "".join(
        f"<li><a href='{escape(u)}'>{escape(k)}</a></li>"
        for k, u in (report.get("links") or {}).items()
    )
    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Playbook Builder E2E — {escape(report['status'])}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 1100px; }}
  .banner {{ padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; }}
  .banner.status-ok {{ background: #ecfdf5; border: 1px solid #6ee7b7; }}
  .banner.status-warn {{ background: #fffbeb; border: 1px solid #fcd34d; }}
  .banner.status-error {{ background: #fef2f2; border: 1px solid #fca5a5; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 8px 10px; vertical-align: top; }}
  th {{ background: #f9fafb; text-align: left; }}
  .msg {{ color: #4b5563; font-size: 13px; margin-top: 4px; }}
  .manual {{ color: #6b7280; font-size: 12px; margin-top: 6px; font-style: italic; }}
  tr.status-error td:first-child {{ color: #dc2626; font-weight: bold; }}
  tr.status-warn td:first-child {{ color: #d97706; font-weight: bold; }}
  tr.status-ok td:first-child {{ color: #059669; font-weight: bold; }}
  tr.status-manual td:first-child {{ color: #6b7280; }}
</style>
</head><body>
<h1>Playbook Builder — E2E validation</h1>
<div class="banner status-{escape(report['status'])}">
  <strong>Overall: {escape(report['status'].upper())}</strong> · Mode {escape(report['mode'])} · {escape(report['timestamp'])}
  <br/>ok {report['summary']['ok']} · warn {report['summary']['warn']} · error {report['summary']['error']} · manual {report['summary']['manual']}
</div>
<h2>Quick links</h2><ul>{quick}</ul>
<h2>All checks</h2>
<table>
<thead><tr><th></th><th>Phase</th><th>Check</th><th>Link</th><th>Type</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</body></html>"""
    path.write_text(html, encoding="utf-8")


def load_ctx_from_env(args: argparse.Namespace) -> E2EContext:
    soar_url = (
        os.environ.get("SOAR_URL")
        or os.environ.get("SOAR_BASE_URL")
        or os.environ.get("PHANTOM_URL")
        or ""
    ).strip()
    soar_user = (
        os.environ.get("SOAR_USER")
        or os.environ.get("SOAR_USERNAME")
        or ""
    ).strip()
    soar_password = (
        os.environ.get("SOAR_PASSWORD")
        or os.environ.get("SOAR_PASS")
        or ""
    ).strip()
    return E2EContext(
        soar_url=soar_url,
        soar_user=soar_user,
        soar_password=soar_password,
        verify_ssl=os.environ.get("SOAR_VERIFY_SSL", "false").lower() in ("1", "true", "yes"),
        asset_name=os.environ.get("PB_ASSET", os.environ.get("ASSET", "mcpbridge")).strip(),
        mcp_bridge_url=os.environ.get("MCP_BRIDGE_URL", "").strip(),
        mode=args.mode.upper() if args.mode else os.environ.get("E2E_MODE", "auto").upper(),
        skip_import=args.skip_import,
        cleanup_import=not args.no_cleanup,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E validate SOAR Playbook Builder")
    parser.add_argument("--mode", choices=["auto", "A", "B", "a", "b"], default="auto",
                        help="A=templates only, B=require bridge, auto=warn on bridge")
    parser.add_argument("--skip-import", action="store_true", help="Skip import playbook step")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep imported E2E playbook")
    parser.add_argument("--report-dir", default="dist/e2e", help="Write reports here")
    parser.add_argument(
        "--phases",
        default="",
        help="Comma-separated phase ids (e.g. 3-sidecar-api,4-import)",
    )
    args = parser.parse_args()
    if args.mode.lower() == "a":
        args.mode = "A"
    elif args.mode.lower() == "b":
        args.mode = "B"

    ctx = load_ctx_from_env(args)
    phases = (
        {p.strip() for p in args.phases.split(",") if p.strip()}
        if getattr(args, "phases", None) and args.phases.strip()
        else None
    )
    report = run_e2e(ctx, phases=phases)

    out_dir = Path(args.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "e2e-report.json"
    md_path = out_dir / "e2e-report.md"
    html_path = out_dir / "e2e-report.html"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, md_path)
    _write_html(report, html_path)

    print(f"Overall: {report['status']}")
    print(f"Reports: {html_path}")
    print(f"         {md_path}")
    print(f"         {json_path}")
    print()
    for c in report["checks"]:
        if c["status"] in ("error", "warn"):
            print(f"  {_status_icon(c['status'])} [{c['phase']}] {c['title']}: {c['message']}")
            if c.get("verify_url"):
                print(f"      → {c['verify_url']}")

    return 1 if report["summary"].get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
