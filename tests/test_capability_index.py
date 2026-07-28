"""Tests for capability index (air-gap spec step 1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from capability.index import (  # noqa: E402
    build_index,
    index_status,
    load_baseline_apps,
    load_baseline_cef,
    load_egress_substitutions,
    load_egress_tags,
    load_index,
    merge_baseline,
)
from capability.introspect import harvest_all  # noqa: E402
from capability.schema import AppCapability, CapabilityIndex  # noqa: E402


def test_baseline_apps_include_phantom_and_pagerduty():
    apps = load_baseline_apps()
    assert "phantom" in apps
    assert "pagerduty" in apps
    phantom = apps["phantom"]
    names = {a.name for a in phantom.actions}
    assert "add note" in names
    assert "set severity" in names


def test_egress_tags_mark_external_reputation():
    tags = load_egress_tags()
    assert tags["virustotalv3"]["file reputation"] == "true"
    assert tags["phantom"]["add note"] == "false"


def test_merge_preserves_baseline_when_not_discovered():
    baseline = load_baseline_apps()
    empty = CapabilityIndex(
        apps={},
        cef_fields=load_baseline_cef(),
        harvest_status="failed",
        harvest_errors=["offline"],
    )
    merged = merge_baseline(empty)
    assert "microsoft_teams" in merged.apps
    assert merged.apps["microsoft_teams"].source == "baseline"


def test_merge_marks_discovered_plus_baseline_as_merged():
    baseline = load_baseline_apps()
    disc = CapabilityIndex(
        apps={
            "phantom": AppCapability(
                name="phantom",
                version="6.2.0",
                actions=baseline["phantom"].actions,
                source="discovered",
            )
        },
        cef_fields=[],
        harvest_status="partial",
    )
    merged = merge_baseline(disc)
    assert merged.apps["phantom"].source == "merged"
    assert merged.apps["slack"].source == "baseline"


def test_build_index_offline_persists():
    tmp = ROOT / "capability" / ".index" / "test_capability_index.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if tmp.exists():
        tmp.unlink()
    index, saved = build_index(
        rest_fn=lambda *_a, **_k: (False, "offline test"),
        persist=True,
        path=tmp,
    )
    assert saved is not None
    assert saved.is_file()
    assert "phantom" in index.apps
    reloaded = load_index(path=tmp)
    assert reloaded is not None
    assert reloaded.index_version == index.index_version
    status = index_status(path=tmp)
    assert status["loaded"] is True
    assert status["action_count"] >= 5
    tmp.unlink(missing_ok=True)


def test_harvest_all_offline_returns_errors():
    index = harvest_all(rest_fn=lambda *_a, **_k: (False, "no rest"))
    assert index.harvest_status in ("failed", "partial", "ok")
    assert index.harvest_errors


def test_egress_substitutions_present():
    subs = load_egress_substitutions()
    assert "virustotalv3:file reputation" in subs


def test_capability_index_roundtrip_json():
    apps = load_baseline_apps()
    index = CapabilityIndex(apps=apps, cef_fields=load_baseline_cef(), index_version="abc")
    blob = json.dumps(index.to_dict())
    restored = CapabilityIndex.from_dict(json.loads(blob))
    assert restored.index_version == "abc"
    assert "phantom" in restored.apps


if __name__ == "__main__":
    tests = [
        test_baseline_apps_include_phantom_and_pagerduty,
        test_egress_tags_mark_external_reputation,
        test_merge_preserves_baseline_when_not_discovered,
        test_merge_marks_discovered_plus_baseline_as_merged,
        test_build_index_offline_persists,
        test_harvest_all_offline_returns_errors,
        test_egress_substitutions_present,
        test_capability_index_roundtrip_json,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\nAll {len(tests)} capability index tests passed")
