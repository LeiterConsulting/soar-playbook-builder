#!/usr/bin/env python3
"""Eval harness — gating dependency for air-gap playbook builder modules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capability.index import (  # noqa: E402
    build_index,
    index_status,
    load_baseline_apps,
    load_baseline_cef,
    load_egress_tags,
    load_index,
    merge_baseline,
)
from capability.introspect import harvest_all  # noqa: E402
from capability.schema import CapabilityIndex  # noqa: E402


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def suite_capability() -> None:
    """Step 1 gate — capability index schema, baseline, merge, persistence."""
    baseline = load_baseline_apps()
    if len(baseline) < 3:
        _fail(f"baseline apps too small: {len(baseline)}")
    _ok(f"baseline apps loaded ({len(baseline)})")

    cef = load_baseline_cef()
    if len(cef) < 5:
        _fail(f"baseline cef too small: {len(cef)}")
    _ok(f"baseline cef loaded ({len(cef)} fields)")

    egress = load_egress_tags()
    if "phantom" not in egress:
        _fail("egress_tags missing phantom")
    if egress.get("virustotalv3", {}).get("file reputation") != "true":
        _fail("virustotal file reputation must require egress")
    _ok("egress tags loaded")

    # Offline harvest (no REST) should still produce baseline-backed index
    discovered = harvest_all(rest_fn=lambda *_a, **_k: (False, "offline"), baseline_cef=cef)
    empty = CapabilityIndex(
        built_at=discovered.built_at,
        harvest_status="failed",
        harvest_errors=discovered.harvest_errors,
        apps=baseline,
        assets=[],
        cef_fields=cef,
        labels=["events"],
        severities=["low", "medium", "high", "critical"],
        statuses=["new", "open", "closed"],
    )
    merged = merge_baseline(empty)
    if "pagerduty" not in merged.apps:
        _fail("merged index missing pagerduty baseline app")
    pd = merged.apps["pagerduty"]
    create = next((a for a in pd.actions if a.name == "create incident"), None)
    if not create or create.requires_egress != "true":
        _fail("pagerduty create incident egress tag wrong")
    _ok("baseline merge preserves egress tags")

    tmp = Path(__file__).resolve().parent / ".tmp_capability_index.json"
    index, saved = build_index(rest_fn=lambda *_a, **_k: (False, "offline"), persist=True, path=tmp)
    if saved is None or not saved.is_file():
        _fail("build_index did not persist")
    loaded = load_index(path=tmp)
    if loaded is None or "phantom" not in loaded.apps:
        _fail("reload index missing phantom")
    _ok(f"index persist + reload ({saved.name})")

    status = index_status(path=tmp)
    if status["app_count"] < 3:
        _fail(f"index_status app_count: {status['app_count']}")
    _ok(f"index_status app_count={status['app_count']} action_count={status['action_count']}")

    tmp.unlink(missing_ok=True)
    print("\nSuite capability: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="SOAR Playbook Builder eval harness")
    parser.add_argument("--suite", default="capability", choices=["capability"])
    args = parser.parse_args()
    if args.suite == "capability":
        suite_capability()
    else:
        _fail(f"unknown suite: {args.suite}")


if __name__ == "__main__":
    main()
