#!/usr/bin/env python3
"""
Vet every Playbook Builder template — structural (offline) and optional live SOAR runtime.

Usage:
  python scripts/runtime_validate.py                    # structural only
  source scripts/env.e2e.local && python scripts/runtime_validate.py --live --mode safe
  python scripts/runtime_validate.py --live --transport mcp --mode integration
  python scripts/runtime_validate.py --live --mode destructive   # requires RUN_DESTRUCTIVE=1

Reports: dist/runtime-vet/report.json + report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "soar_playbook_builder"
sys.path.insert(0, str(PKG))

# Allow MCP transport when mcp-for-splunk repo is sibling
MCP_ROOT = ROOT.parent.parent
if (MCP_ROOT / "mcp_soar").is_dir():
    sys.path.insert(0, str(MCP_ROOT))

from runtime_validate import (  # noqa: E402
    RuntimeContext,
    render_markdown_report,
    run_live_vet,
    run_structural_vet,
    summarize_checks,
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def main() -> int:
    parser = argparse.ArgumentParser(description="Vet all Playbook Builder templates")
    parser.add_argument("--live", action="store_true", help="Run live SOAR runtime vet (requires credentials)")
    parser.add_argument(
        "--mode",
        choices=("safe", "integration", "destructive", "structural-only"),
        default="safe",
        help="Runtime tier filter (default: safe)",
    )
    parser.add_argument(
        "--transport",
        choices=("rest", "mcp"),
        default="rest",
        help="SOAR API transport for playbook_run (mcp uses mcp_soar SOARClient)",
    )
    parser.add_argument("--pattern", action="append", dest="patterns", help="Limit to pattern id(s)")
    parser.add_argument("--report-dir", default=str(ROOT / "dist" / "runtime-vet"))
    parser.add_argument("--no-cleanup", action="store_true", help="Keep imported playbooks and containers")
    parser.add_argument("--poll-timeout", type=float, default=120.0)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    args = parser.parse_args()

    _load_env_file(ROOT / "scripts" / "env.e2e.local")

    runtime_mode = args.mode
    if args.live and runtime_mode == "structural-only":
        runtime_mode = "safe"

    if runtime_mode == "destructive" and not _env_bool("RUN_DESTRUCTIVE"):
        print(
            "Refusing --mode destructive without RUN_DESTRUCTIVE=1 "
            "(integration actions may disable accounts, block IPs, etc.)",
            file=sys.stderr,
        )
        return 2

    ctx = RuntimeContext(
        soar_url=os.environ.get("SOAR_URL", "").strip(),
        soar_user=os.environ.get("SOAR_USER", "").strip(),
        soar_password=os.environ.get("SOAR_PASSWORD", "").strip(),
        verify_ssl=_env_bool("SOAR_VERIFY_SSL", False),
        asset_name=os.environ.get("PB_ASSET", "mcpbridge").strip(),
        transport=args.transport,
        runtime_mode=runtime_mode if args.live else "structural-only",
        cleanup=not args.no_cleanup,
        poll_seconds=args.poll_interval,
        poll_timeout=args.poll_timeout,
        mcp_bridge_url=os.environ.get("MCP_BRIDGE_URL", "").strip(),
    )

    checks = run_structural_vet()
    if args.live:
        if not ctx.soar_url or not ctx.soar_user or not ctx.soar_password:
            print("Set SOAR_URL, SOAR_USER, SOAR_PASSWORD (scripts/env.e2e.local)", file=sys.stderr)
            return 2
        checks.extend(run_live_vet(ctx, args.patterns))

    report = summarize_checks(checks)
    report["live"] = args.live
    report["runtime_mode"] = ctx.runtime_mode
    report["transport"] = ctx.transport

    out_dir = Path(args.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown_report(report, ctx), encoding="utf-8")

    summ = report["summary"]
    print(
        f"Runtime vet: {report['status']} — "
        f"ok={summ.get('ok')} warn={summ.get('warn')} error={summ.get('error')} skipped={summ.get('skipped')}"
    )
    print(f"Reports: {out_dir / 'report.md'}")

    if report["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
