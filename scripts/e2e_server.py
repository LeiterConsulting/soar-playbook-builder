#!/usr/bin/env python3
"""Local API server for the E2E Validation Console (React UI)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from e2e_validate import (  # noqa: E402
    PHASE_IDS,
    _write_html,
    _write_markdown,
    load_ctx_from_env,
    run_e2e,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

ROOT = _SCRIPTS.parent
REPO_ROOT = ROOT.parent.parent

_SOAR_ENV_KEYS = frozenset({
    "SOAR_URL", "SOAR_BASE_URL", "SOAR_USER", "SOAR_USERNAME",
    "SOAR_PASSWORD", "SOAR_PASS", "SOAR_VERIFY_SSL",
    "PB_ASSET", "ASSET", "E2E_MODE", "MCP_BRIDGE_URL",
})

_PLACEHOLDER_URL_MARKERS = ("your-soar.example.com", "example.com:8443")
_PLACEHOLDER_PASSWORDS = frozenset({"change-me", ""})


def _is_placeholder_soar_url(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return True
    return any(marker in v for marker in _PLACEHOLDER_URL_MARKERS)


def _is_placeholder_password(value: str) -> bool:
    return (value or "").strip() in _PLACEHOLDER_PASSWORDS


def _parse_env_file(path: Path, *, overwrite_keys: frozenset[str] | None = None) -> None:
    if not path.is_file():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            cleaned = val.strip().strip('"').strip("'")
            if overwrite_keys is not None:
                if key in overwrite_keys:
                    os.environ[key] = cleaned
            elif key not in os.environ:
                os.environ[key] = cleaned


def _apply_sidecar_env_fallback() -> None:
    """Map sidecar-ui/.env.local VITE_* vars when SOAR creds are missing or placeholders."""
    sidecar = ROOT / "sidecar-ui" / ".env.local"
    if not sidecar.is_file():
        return
    mapping = {
        "VITE_SOAR_URL": "SOAR_URL",
        "VITE_SOAR_USER": "SOAR_USER",
        "VITE_SOAR_PASS": "SOAR_PASSWORD",
    }
    parsed: dict[str, str] = {}
    with open(sidecar, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            parsed[key.strip()] = val.strip().strip('"').strip("'")
    if _is_placeholder_soar_url(os.environ.get("SOAR_URL", "")):
        url = parsed.get("VITE_SOAR_URL", "").strip()
        if url:
            os.environ["SOAR_URL"] = url
    if not (os.environ.get("SOAR_USER") or "").strip():
        user = parsed.get("VITE_SOAR_USER", "").strip()
        if user:
            os.environ["SOAR_USER"] = user
    if _is_placeholder_password(os.environ.get("SOAR_PASSWORD", "")):
        pw = parsed.get("VITE_SOAR_PASS", "").strip()
        if pw:
            os.environ["SOAR_PASSWORD"] = pw


def _load_env_files() -> None:
    e2e_local = ROOT / "scripts" / "env.e2e.local"
    if e2e_local.is_file():
        _parse_env_file(e2e_local, overwrite_keys=_SOAR_ENV_KEYS)
    for candidate in (
        os.environ.get("E2E_ENV", ""),
        str(REPO_ROOT / ".env"),
        str(REPO_ROOT / ".env.secrets"),
    ):
        if candidate and Path(candidate).is_file():
            _parse_env_file(Path(candidate))
    _apply_sidecar_env_fallback()


def _config_snapshot() -> dict[str, Any]:
    soar_url = (
        os.environ.get("SOAR_URL")
        or os.environ.get("SOAR_BASE_URL")
        or ""
    ).strip()
    user = (os.environ.get("SOAR_USER") or os.environ.get("SOAR_USERNAME") or "").strip()
    password = (
        os.environ.get("SOAR_PASSWORD") or os.environ.get("SOAR_PASS") or ""
    ).strip()
    missing = [k for k, v in {
        "SOAR_URL": soar_url,
        "SOAR_USER": user,
        "SOAR_PASSWORD": password,
    }.items() if not v]
    return {
        "soarUrl": soar_url,
        "soarUser": user,
        "hasPassword": bool(password),
        "verifySsl": os.environ.get("SOAR_VERIFY_SSL", "false"),
        "assetName": os.environ.get("PB_ASSET") or os.environ.get("ASSET") or "mcpbridge",
        "mcpBridgeUrl": os.environ.get("MCP_BRIDGE_URL", "http://127.0.0.1:8003/agent"),
        "e2eMode": os.environ.get("E2E_MODE", "auto"),
        "envReady": len(missing) == 0,
        "missingEnv": missing,
        "phases": list(PHASE_IDS),
    }


def _build_ctx(body: dict[str, Any]):
    import argparse

    ns = argparse.Namespace(
        mode=str(body.get("mode") or os.environ.get("E2E_MODE", "auto")),
        skip_import=bool(body.get("skipImport")),
        no_cleanup=bool(body.get("noCleanup")),
        report_dir=str(body.get("reportDir") or "dist/e2e"),
        phases="",
    )
    ctx = load_ctx_from_env(ns)
    if body.get("skipImport"):
        ctx.skip_import = True
    if body.get("noCleanup"):
        ctx.cleanup_import = False
    mode = str(body.get("mode") or ctx.mode).upper()
    if mode in ("A", "B", "AUTO"):
        ctx.mode = mode
    phases_raw = body.get("phases")
    phases = None
    if isinstance(phases_raw, list) and phases_raw:
        phases = {str(p) for p in phases_raw}
    elif isinstance(phases_raw, str) and phases_raw.strip():
        phases = {p.strip() for p in phases_raw.split(",") if p.strip()}
    return ctx, phases


def _cors_headers(request: Request) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "playbook-builder-e2e-console"}, headers=_cors_headers(request))


async def config_api(request: Request) -> JSONResponse:
    _load_env_files()
    return JSONResponse(_config_snapshot(), headers=_cors_headers(request))


async def run_sync(request: Request) -> JSONResponse:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_cors_headers(request))
    _load_env_files()
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    ctx, phases = _build_ctx(body if isinstance(body, dict) else {})
    report = run_e2e(ctx, phases=phases)
    out_dir = ROOT / "dist" / "e2e"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_markdown(report, out_dir / "e2e-report.md")
    _write_html(report, out_dir / "e2e-report.html")
    (out_dir / "e2e-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return JSONResponse(report, headers=_cors_headers(request))


async def run_stream(request: Request) -> StreamingResponse:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_cors_headers(request))
    _load_env_files()
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}

    ctx, phases = _build_ctx(body if isinstance(body, dict) else {})
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def on_check(data: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("check", data))

    def worker() -> None:
        try:
            report = run_e2e(ctx, on_check=on_check, phases=phases)
            out_dir = ROOT / "dist" / "e2e"
            out_dir.mkdir(parents=True, exist_ok=True)
            _write_markdown(report, out_dir / "e2e-report.md")
            _write_html(report, out_dir / "e2e-report.html")
            (out_dir / "e2e-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            loop.call_soon_threadsafe(queue.put_nowait, ("done", report))
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": str(exc)}))

    threading.Thread(target=worker, daemon=True).start()

    async def event_gen():
        while True:
            kind, payload = await queue.get()
            if kind == "check":
                yield f"event: check\ndata: {json.dumps(payload)}\n\n"
            elif kind == "done":
                yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                break
            elif kind == "error":
                yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                break

    headers = _cors_headers(request)
    headers["Cache-Control"] = "no-cache"
    headers["Connection"] = "keep-alive"
    headers["X-Accel-Buffering"] = "no"
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)


async def report_html(request: Request) -> Response:
    path = ROOT / "dist" / "e2e" / "e2e-report.html"
    if not path.is_file():
        return JSONResponse({"error": "No report yet — run validation first"}, status_code=404)
    return Response(path.read_text(encoding="utf-8"), media_type="text/html", headers=_cors_headers(request))


app = Starlette(
    routes=[
        Route("/api/health", health, methods=["GET", "OPTIONS"]),
        Route("/api/config", config_api, methods=["GET", "OPTIONS"]),
        Route("/api/e2e/run", run_sync, methods=["POST", "OPTIONS"]),
        Route("/api/e2e/stream", run_stream, methods=["POST", "OPTIONS"]),
        Route("/api/e2e/report.html", report_html, methods=["GET", "OPTIONS"]),
    ],
)


def main() -> None:
    import uvicorn

    _load_env_files()
    port = int(os.environ.get("E2E_CONSOLE_PORT", "8765"))
    print(f"E2E console API on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
