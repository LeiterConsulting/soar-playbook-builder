"""Structural and live SOAR runtime vetting for all playbook templates."""

from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from asset_resolver import extract_required_asset_keys
from builder_helpers import SCAFFOLDS, analyze_playbook, scaffold_pattern
from coa_builder import build_modern_playbook_json
from local_nl_build import match_pattern
from pattern_catalog import PATTERN_CATALOG, catalog_by_id, catalog_ids
from preview_visual import extract_phantom_acts_with_context
from runtime_fixtures import RUNTIME_FIXTURES, RuntimeFixture, fixture_for

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

VetStatus = Literal["ok", "warn", "error", "skipped"]
Transport = Literal["rest", "mcp"]
RuntimeMode = Literal["safe", "integration", "destructive", "structural-only"]

PLAYBOOK_BUILDER_APPID = "a7c3e891-4f2d-4b18-9e6a-1d5f8c2b0e47"
RUNTIME_PB_PREFIX = "PB_RT_"
TERMINAL_RUN_STATUSES = frozenset({"complete", "completed", "success", "succeeded", "failed", "canceled", "cancelled"})


@dataclass
class VetCheck:
    id: str
    pattern_id: str
    phase: str
    title: str
    status: VetStatus
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeContext:
    soar_url: str
    soar_user: str
    soar_password: str
    verify_ssl: bool
    asset_name: str
    transport: Transport
    runtime_mode: RuntimeMode
    cleanup: bool
    poll_seconds: float
    poll_timeout: float
    mcp_bridge_url: str = ""
    directory: str = ""
    app_version: str = ""


def _action_functions_in_source(source: str) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)}


def _coa_action_func_names(meta: dict) -> list[str]:
    nodes = meta.get("coa", {}).get("data", {}).get("nodes", {})
    return [
        n["data"]["functionName"]
        for n in nodes.values()
        if n.get("type") == "action" and n.get("data", {}).get("functionName")
    ]


def run_structural_vet() -> list[VetCheck]:
    """Offline vet — same coverage as tests/test_all_patterns.py."""
    checks: list[VetCheck] = []
    from asset_resolver import ASSET_TYPE_HINTS

    for pid in catalog_ids():
        meta = catalog_by_id().get(pid, {})
        label = meta.get("label") or pid

        if pid not in SCAFFOLDS:
            checks.append(
                VetCheck(
                    id=f"{pid}_scaffold",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — scaffold registered",
                    status="error",
                    message=f"Missing from SCAFFOLDS",
                )
            )
            continue

        if pid not in RUNTIME_FIXTURES:
            checks.append(
                VetCheck(
                    id=f"{pid}_fixture",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — runtime fixture",
                    status="warn",
                    message="No runtime fixture — live run will be skipped",
                )
            )

        result = scaffold_pattern(pid)
        if result.get("status") != "success":
            checks.append(
                VetCheck(
                    id=f"{pid}_scaffold",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — scaffold loads",
                    status="error",
                    message=str(result.get("error") or result.get("status")),
                )
            )
            continue

        source = SCAFFOLDS[pid]
        analysis = analyze_playbook(source)
        if not analysis["valid_python"]:
            checks.append(
                VetCheck(
                    id=f"{pid}_python",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — valid Python",
                    status="error",
                    message="Invalid Python syntax",
                )
            )
            continue

        score = analysis["score"]
        py_status: VetStatus = "ok" if score >= 75 else "warn"
        checks.append(
            VetCheck(
                id=f"{pid}_python",
                pattern_id=pid,
                phase="structural",
                title=f"{label} — Python analysis",
                status=py_status,
                message=f"score={score}, functions={analysis.get('functions')}",
            )
        )

        try:
            coa_meta = build_modern_playbook_json(source, pid, pattern=pid)
            json.dumps(coa_meta)
            node_types = {n.get("type") for n in coa_meta["coa"]["data"]["nodes"].values()}
            coa_ok = "filter" not in node_types and "start" in node_types and "end" in node_types
            coa_funcs = _coa_action_func_names(coa_meta)
            source_funcs = _action_functions_in_source(source)
            missing = [fn for fn in coa_funcs if fn not in source_funcs]
            checks.append(
                VetCheck(
                    id=f"{pid}_coa",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — COA / VPE JSON",
                    status="ok" if coa_ok and not missing else "error",
                    message="COA valid"
                    if coa_ok and not missing
                    else f"coa_ok={coa_ok}, missing_funcs={missing}",
                )
            )
        except Exception as exc:
            checks.append(
                VetCheck(
                    id=f"{pid}_coa",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — COA / VPE JSON",
                    status="error",
                    message=str(exc),
                )
            )

        funcs = _action_functions_in_source(source)
        bad_callbacks: list[str] = []
        for act in extract_phantom_acts_with_context(source):
            cb = act.get("callback")
            if cb and cb not in ("None", "on_finish") and cb not in funcs:
                bad_callbacks.append(cb)
        checks.append(
            VetCheck(
                id=f"{pid}_callbacks",
                pattern_id=pid,
                phase="structural",
                title=f"{label} — phantom.act callbacks",
                status="ok" if not bad_callbacks else "error",
                message="All callbacks bound" if not bad_callbacks else f"Missing: {bad_callbacks}",
            )
        )

        missing_hints = [
            k
            for k in extract_required_asset_keys(source)
            if k != "soar" and k not in ASSET_TYPE_HINTS
        ]
        checks.append(
            VetCheck(
                id=f"{pid}_assets",
                pattern_id=pid,
                phase="structural",
                title=f"{label} — asset resolver hints",
                status="ok" if not missing_hints else "warn",
                message="OK" if not missing_hints else f"No hints for: {missing_hints}",
                detail={"asset_keys": extract_required_asset_keys(source)},
            )
        )

        fix = fixture_for(pid)
        if fix and fix.nl_prompt:
            got = match_pattern(fix.nl_prompt)
            nl_status: VetStatus = "ok" if got == pid else "warn"
            checks.append(
                VetCheck(
                    id=f"{pid}_nl_route",
                    pattern_id=pid,
                    phase="structural",
                    title=f"{label} — offline NL routing",
                    status=nl_status,
                    message=f"match_pattern → {got!r}",
                )
            )

    return checks


def _rest_client(ctx: RuntimeContext, timeout: float = 60.0) -> httpx.Client:
    if httpx is None:
        raise RuntimeError("httpx required — pip install httpx")
    return httpx.Client(
        base_url=ctx.soar_url.rstrip("/"),
        auth=(ctx.soar_user, ctx.soar_password),
        verify=ctx.verify_ssl,
        timeout=timeout,
        headers={"Accept": "application/json"},
        trust_env=False,
    )


def _handler_url(ctx: RuntimeContext, query: str = "") -> str:
    base = f"{ctx.soar_url.rstrip('/')}/rest/handler/{ctx.directory}/{ctx.asset_name}/chat"
    return f"{base}?{query}" if query else base


def _resolve_pb_app(client: httpx.Client) -> tuple[str, str]:
    r = client.get("/rest/app", params={"_page_size": 200})
    r.raise_for_status()
    apps = r.json().get("data") if isinstance(r.json(), dict) else []
    app_row = None
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
        raise RuntimeError("Playbook Builder app not found — install soar_playbook_builder.tgz")
    directory = str(app_row.get("directory") or "")
    if not directory:
        raise RuntimeError("Playbook Builder app has empty directory — reinstall .tgz")
    return directory, str(app_row.get("app_version") or "0")


def _sidecar_get(ctx: RuntimeContext, client: httpx.Client, query: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        r = client.get(_handler_url(ctx, query), headers={"Accept": "application/json"})
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def _sidecar_post(ctx: RuntimeContext, client: httpx.Client, body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        r = client.post(
            _handler_url(ctx),
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120.0,
        )
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def _extract_id(resp: dict[str, Any] | list[Any] | None) -> int | None:
    if resp is None:
        return None
    if isinstance(resp, list) and resp:
        first = resp[0]
        if isinstance(first, dict) and first.get("id") is not None:
            return int(first["id"])
    if isinstance(resp, dict):
        if resp.get("id") is not None:
            return int(resp["id"])
        data = resp.get("data")
        if isinstance(data, list) and data:
            row = data[0]
            if isinstance(row, dict) and row.get("id") is not None:
                return int(row["id"])
    return None


def _create_container(client: httpx.Client, fixture: RuntimeFixture, tag: str) -> tuple[int | None, str | None]:
    import os

    reuse = os.getenv("RUNTIME_CONTAINER_ID", "").strip()
    if reuse.isdigit():
        return int(reuse), None

    body = {
        "name": f"{RUNTIME_PB_PREFIX}{fixture.pattern_id}_{tag}",
        "description": f"Runtime validation for {fixture.pattern_id}",
        "label": "pb_runtime",
        "severity": fixture.container_severity,
        "status": "new",
    }
    try:
        r = client.post("/rest/container", json=body)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        cid = _extract_id(r.json())
        if cid is None:
            return None, f"Unexpected container response: {str(r.text)[:200]}"
        return cid, None
    except Exception as exc:
        return None, str(exc)


def _create_artifacts(client: httpx.Client, container_id: int, fixture: RuntimeFixture) -> str | None:
    for art in fixture.artifacts:
        cef = art.get("cef") or {}
        cef_types = {k: [""] for k in cef.keys()}
        body = {
            "container_id": container_id,
            "name": art.get("name") or "artifact",
            "label": art.get("label") or "event",
            "severity": "Medium",
            "cef": cef,
            "cef_types": cef_types,
        }
        try:
            r = client.post("/rest/artifact", json=body)
            if r.status_code >= 400:
                return f"artifact HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            return str(exc)
    return None


def _run_playbook_rest(client: httpx.Client, container_id: int, playbook_id: int) -> tuple[int | None, str | None]:
    body = {"container_id": container_id, "playbook_id": playbook_id, "run": True}
    try:
        r = client.post("/rest/playbook_run", json=body)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        run_id = _extract_id(r.json())
        if run_id is None:
            data = r.json()
            if isinstance(data, dict):
                run_id = data.get("playbook_run_id") or data.get("run_id")
                if run_id is not None:
                    return int(run_id), None
            return None, f"Unexpected playbook_run response: {str(r.text)[:200]}"
        return run_id, None
    except Exception as exc:
        return None, str(exc)


def _run_playbook_mcp(ctx: RuntimeContext, container_id: int, playbook_id: int) -> tuple[int | None, str | None]:
    import asyncio

    from mcp_soar.client.http_client import SOARClient
    from mcp_soar.config.headers import SOARRequestConfig

    cfg = SOARRequestConfig(
        base_url=ctx.soar_url.rstrip("/"),
        soar_username=ctx.soar_user,
        soar_password=ctx.soar_password,
        verify_ssl=ctx.verify_ssl,
    )

    async def _go() -> tuple[int | None, str | None]:
        body = {"container_id": container_id, "playbook_id": playbook_id, "run": True}
        try:
            async with SOARClient(cfg, timeout=90.0) as client:
                result = await client.post_json("/rest/playbook_run", body)
            run_id = _extract_id(result)
            if run_id is None and isinstance(result, dict):
                rid = result.get("playbook_run_id") or result.get("run_id")
                if rid is not None:
                    return int(rid), None
            if run_id is None:
                return None, f"Unexpected MCP playbook_run response: {str(result)[:200]}"
            return run_id, None
        except Exception as exc:
            return None, str(exc)

    return asyncio.run(_go())


def _poll_playbook_run(client: httpx.Client, run_id: int, timeout: float, interval: float) -> tuple[dict[str, Any] | None, str | None]:
    deadline = time.time() + timeout
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        try:
            r = client.get(f"/rest/playbook_run/{run_id}")
            if r.status_code >= 400:
                return None, f"poll HTTP {r.status_code}: {r.text[:200]}"
            data = r.json()
            row = data
            if isinstance(data, dict) and isinstance(data.get("data"), list) and data["data"]:
                row = data["data"][0]
            if isinstance(row, dict):
                last = row
                status = str(row.get("status") or "").lower()
                if status in TERMINAL_RUN_STATUSES:
                    return row, None
        except Exception as exc:
            return last, str(exc)
        time.sleep(interval)
    return last, f"Timed out after {timeout}s (last status={last.get('status') if last else 'unknown'})"


def _count_notes(client: httpx.Client, container_id: int) -> int:
    try:
        r = client.get(
            "/rest/note",
            params={"_page_size": 50, "_filter": f'container_id="{container_id}"'},
        )
        if r.status_code >= 400:
            return 0
        data = r.json()
        rows = data.get("data") if isinstance(data, dict) else []
        return len(rows or [])
    except Exception:
        return 0


def _list_action_runs(client: httpx.Client, container_id: int, playbook_run_id: int | None) -> list[dict[str, Any]]:
    filt = f'container_id="{container_id}"'
    if playbook_run_id:
        filt += f' and playbook_run_id="{playbook_run_id}"'
    try:
        r = client.get("/rest/action_run", params={"_page_size": 100, "_filter": filt})
        if r.status_code >= 400:
            return []
        data = r.json()
        return list(data.get("data") or []) if isinstance(data, dict) else []
    except Exception:
        return []


def _cleanup_resources(client: httpx.Client, playbook_id: int | None, container_id: int | None) -> None:
    if playbook_id:
        try:
            client.delete(f"/rest/playbook/{playbook_id}")
        except Exception:
            pass
    if container_id:
        try:
            client.delete(f"/rest/container/{container_id}")
        except Exception:
            pass


def _vet_one_pattern_live(
    ctx: RuntimeContext,
    client: httpx.Client,
    fixture: RuntimeFixture,
    tag: str,
) -> list[VetCheck]:
    pid = fixture.pattern_id
    meta = catalog_by_id().get(pid, {})
    label = meta.get("label") or pid
    checks: list[VetCheck] = []
    playbook_id: int | None = None
    container_id: int | None = None
    run_id: int | None = None

    def add(check_id: str, title: str, status: VetStatus, message: str, **detail: Any) -> None:
        checks.append(
            VetCheck(
                id=f"{pid}_{check_id}",
                pattern_id=pid,
                phase="live",
                title=f"{label} — {title}",
                status=status,
                message=message,
                detail=dict(detail),
            )
        )

    if not fixture.allowed_in_mode(ctx.runtime_mode):
        add(
            "runtime_skip",
            "runtime tier",
            "skipped",
            f"Tier {fixture.tier} not included in --mode {ctx.runtime_mode}",
        )
        return checks

    data, err = _sidecar_get(ctx, client, f"action=scaffold&pattern={pid}")
    if err or not data or not data.get("source"):
        add("scaffold", "scaffold via sidecar", "error", err or "empty source")
        return checks
    source = data["source"]
    add("scaffold", "scaffold via sidecar", "ok", f"{len(source)} bytes")

    pb_name = f"{RUNTIME_PB_PREFIX}{pid}_{tag}"
    imp_body = {
        "action": "import_draft",
        "confirm": True,
        "source": source,
        "name": pb_name,
        "pattern": pid,
    }
    imp, err = _sidecar_post(ctx, client, imp_body)
    if err or (imp or {}).get("status") != "success":
        add("import", "import draft", "error", err or str((imp or {}).get("error") or imp))
        return checks
    playbook_id = int(str((imp or {}).get("playbook_id") or "0"))
    add("import", "import draft", "ok", f"playbook_id={playbook_id}")

    container_id, err = _create_container(client, fixture, tag)
    if err or container_id is None:
        add("container", "create container", "error", err or "no id")
        if ctx.cleanup and playbook_id:
            _cleanup_resources(client, playbook_id, None)
        return checks
    add("container", "create container", "ok", f"container_id={container_id}")

    if fixture.artifacts:
        err = _create_artifacts(client, container_id, fixture)
        if err:
            add("artifacts", "seed artifacts", "error", err)
            if ctx.cleanup:
                _cleanup_resources(client, playbook_id, container_id)
            return checks
        add("artifacts", "seed artifacts", "ok", f"{len(fixture.artifacts)} artifact(s)")

    if ctx.transport == "mcp":
        run_id, err = _run_playbook_mcp(ctx, container_id, playbook_id)
        transport_label = "MCP SOARClient"
    else:
        run_id, err = _run_playbook_rest(client, container_id, playbook_id)
        transport_label = "REST"
    if err or run_id is None:
        add("run_start", f"start run ({transport_label})", "error", err or "no run_id")
        if ctx.cleanup:
            _cleanup_resources(client, playbook_id, container_id)
        return checks
    add("run_start", f"start run ({transport_label})", "ok", f"run_id={run_id}")

    run_row, err = _poll_playbook_run(client, run_id, ctx.poll_timeout, ctx.poll_seconds)
    run_status = str((run_row or {}).get("status") or "unknown").lower()
    if err and run_status not in TERMINAL_RUN_STATUSES:
        add("run_poll", "poll playbook run", "error", err, run_id=run_id, run=run_row)
        if ctx.cleanup:
            _cleanup_resources(client, playbook_id, container_id)
        return checks

    success_states = {"complete", "completed", "success", "succeeded"}
    failed = run_status in {"failed", "canceled", "cancelled"}
    expect = fixture.expect
    if expect.playbook_complete and failed:
        run_vet: VetStatus = "error"
        run_msg = f"status={run_status}"
    elif expect.playbook_complete and run_status not in success_states:
        run_vet = "warn"
        run_msg = f"status={run_status} (expected complete)"
    else:
        run_vet = "ok"
        run_msg = f"status={run_status}"

    action_runs = _list_action_runs(client, container_id, run_id)
    action_names = [str(a.get("action") or a.get("action_name") or "") for a in action_runs]
    failed_actions = [a for a in action_runs if str(a.get("status") or "").lower() in ("failed", "error")]

    if expect.action_names:
        missing_actions = [n for n in expect.action_names if not any(n in an for an in action_names)]
        if missing_actions and not expect.allow_action_fail:
            run_vet = "error"
            run_msg += f"; missing actions: {missing_actions}"
        elif missing_actions and expect.allow_action_fail:
            if run_vet == "ok":
                run_vet = "warn"
            run_msg += f"; actions not seen (allowed): {missing_actions}"
        elif failed_actions and not expect.allow_action_fail:
            run_vet = "error"
            run_msg += f"; failed actions: {[a.get('action') for a in failed_actions]}"
        elif failed_actions and expect.allow_action_fail:
            if run_vet == "ok":
                run_vet = "warn"
            run_msg += f"; action failures tolerated: {len(failed_actions)}"

    note_count = _count_notes(client, container_id)
    if expect.min_notes and note_count < expect.min_notes:
        if run_vet == "ok":
            run_vet = "warn"
        run_msg += f"; notes={note_count} (expected ≥{expect.min_notes})"

    add(
        "run_poll",
        "poll playbook run",
        run_vet,
        run_msg,
        run_id=run_id,
        run_status=run_status,
        action_runs=len(action_runs),
        notes=note_count,
        transport=ctx.transport,
    )

    if ctx.cleanup:
        _cleanup_resources(client, playbook_id, container_id)
        add("cleanup", "cleanup", "ok", f"deleted playbook {playbook_id}, container {container_id}")

    return checks


def run_live_vet(ctx: RuntimeContext, pattern_ids: list[str] | None = None) -> list[VetCheck]:
    if httpx is None:
        raise RuntimeError("httpx required — pip install httpx")
    if ctx.runtime_mode == "structural-only":
        return []

    checks: list[VetCheck] = []
    tag = str(int(time.time()))

    with _rest_client(ctx) as client:
        try:
            r = client.get("/rest/version")
            if r.status_code != 200:
                checks.append(
                    VetCheck(
                        id="soar_connect",
                        pattern_id="*",
                        phase="live",
                        title="SOAR REST reachable",
                        status="error",
                        message=f"HTTP {r.status_code}",
                    )
                )
                return checks
        except Exception as exc:
            checks.append(
                VetCheck(
                    id="soar_connect",
                    pattern_id="*",
                    phase="live",
                    title="SOAR REST reachable",
                    status="error",
                    message=str(exc),
                )
            )
            for pid in pattern_ids or catalog_ids():
                checks.append(
                    VetCheck(
                        id=f"{pid}_runtime_skip",
                        pattern_id=pid,
                        phase="live",
                        title=f"{catalog_by_id().get(pid, {}).get('label', pid)} — runtime",
                        status="skipped",
                        message="SOAR unreachable — run from network with lab access",
                    )
                )
            return checks

        try:
            ctx.directory, ctx.app_version = _resolve_pb_app(client)
            checks.append(
                VetCheck(
                    id="pb_app",
                    pattern_id="*",
                    phase="live",
                    title="Playbook Builder app",
                    status="ok",
                    message=f"v{ctx.app_version}, directory={ctx.directory}",
                )
            )
        except Exception as exc:
            checks.append(
                VetCheck(
                    id="pb_app",
                    pattern_id="*",
                    phase="live",
                    title="Playbook Builder app",
                    status="error",
                    message=str(exc),
                )
            )
            return checks

        if ctx.transport == "mcp":
            try:
                from mcp_soar.config.headers import SOARRequestConfig  # noqa: F401
            except ImportError as exc:
                checks.append(
                    VetCheck(
                        id="mcp_import",
                        pattern_id="*",
                        phase="live",
                        title="MCP transport (mcp_soar)",
                        status="error",
                        message=f"mcp_soar not on PYTHONPATH: {exc}",
                    )
                )
                return checks
            checks.append(
                VetCheck(
                    id="mcp_transport",
                    pattern_id="*",
                    phase="live",
                    title="MCP transport",
                    status="ok",
                    message="Using mcp_soar SOARClient for playbook_run",
                )
            )

        targets = pattern_ids or catalog_ids()
        for pid in targets:
            fixture = fixture_for(pid)
            if not fixture:
                checks.append(
                    VetCheck(
                        id=f"{pid}_runtime_skip",
                        pattern_id=pid,
                        phase="live",
                        title=f"{pid} — runtime",
                        status="skipped",
                        message="No runtime fixture defined",
                    )
                )
                continue
            checks.extend(_vet_one_pattern_live(ctx, client, fixture, tag))

    return checks


def summarize_checks(checks: list[VetCheck]) -> dict[str, Any]:
    summary = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    by_pattern: dict[str, dict[str, int]] = {}
    for c in checks:
        summary[c.status] = summary.get(c.status, 0) + 1
        bucket = by_pattern.setdefault(c.pattern_id, {"ok": 0, "warn": 0, "error": 0, "skipped": 0})
        bucket[c.status] = bucket.get(c.status, 0) + 1

    overall: Literal["success", "partial", "error"] = "success"
    if summary["error"]:
        overall = "partial" if summary["ok"] else "error"
    elif summary["warn"]:
        overall = "partial"

    return {
        "status": overall,
        "summary": summary,
        "by_pattern": by_pattern,
        "checks": [c.to_dict() for c in checks],
        "pattern_count": len(PATTERN_CATALOG),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def render_markdown_report(report: dict[str, Any], ctx: RuntimeContext | None = None) -> str:
    lines = [
        "# Playbook template vet report",
        "",
        f"- **Overall:** {report.get('status')}",
        f"- **Generated:** {report.get('generated_at')}",
        f"- **Templates:** {report.get('pattern_count')}",
    ]
    if ctx:
        lines.append(f"- **SOAR:** {ctx.soar_url or '(structural only)'}")
        lines.append(f"- **Mode:** {ctx.runtime_mode}")
        lines.append(f"- **Transport:** {ctx.transport}")
    summ = report.get("summary") or {}
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"| ok | warn | error | skipped |",
            f"|---:|---:|---:|---:|",
            f"| {summ.get('ok', 0)} | {summ.get('warn', 0)} | {summ.get('error', 0)} | {summ.get('skipped', 0)} |",
            "",
            "## By template",
            "",
            "| Template | ok | warn | error | skipped |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    by_pat = report.get("by_pattern") or {}
    for row in PATTERN_CATALOG:
        pid = row["id"]
        b = by_pat.get(pid, {})
        lines.append(
            f"| {row['label']} (`{pid}`) | {b.get('ok', 0)} | {b.get('warn', 0)} | {b.get('error', 0)} | {b.get('skipped', 0)} |"
        )
    lines.extend(["", "## Checks", ""])
    for c in report.get("checks") or []:
        icon = {"ok": "✓", "warn": "!", "error": "✗", "skipped": "–"}.get(c.get("status"), "?")
        lines.append(f"- {icon} **{c.get('title')}** — {c.get('message')}")
    return "\n".join(lines) + "\n"
