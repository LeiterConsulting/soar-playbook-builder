"""Tests for capability index (air-gap spec step 1)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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
    save_index,
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
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory) / "test_capability_index.json"
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


def test_corrupt_index_recovers_last_good(tmp_path: Path):
    target = tmp_path / "capability_index.json"
    first = CapabilityIndex(index_version="first", apps=load_baseline_apps())
    second = CapabilityIndex(index_version="second", apps=load_baseline_apps())
    save_index(first, target)
    save_index(second, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["index_version"] = "tampered"
    target.write_text(json.dumps(payload), encoding="utf-8")

    recovered = load_index(target)
    status = index_status(target)
    assert recovered is not None
    assert recovered.index_version == "first"
    assert status["recovered_from_last_good"] is True
    assert "capability_index.json" in status["integrity_error"]


def test_checksum_mismatch_without_backup_fails_closed(tmp_path: Path):
    target = tmp_path / "capability_index.json"
    save_index(CapabilityIndex(index_version="one", apps=load_baseline_apps()), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["index_version"] = "tampered"
    target.write_text(json.dumps(payload), encoding="utf-8")

    assert load_index(target) is None
    status = index_status(target)
    assert status["loaded"] is False
    assert "checksum mismatch" in status["integrity_error"]


def test_failed_atomic_replace_preserves_current_index(tmp_path: Path):
    target = tmp_path / "capability_index.json"
    first = CapabilityIndex(index_version="first", apps=load_baseline_apps())
    second = CapabilityIndex(index_version="second", apps=load_baseline_apps())
    save_index(first, target)
    before = target.read_bytes()
    real_replace = os.replace

    def replace_with_target_failure(source, destination):
        if Path(destination) == target:
            raise OSError("simulated replace failure")
        return real_replace(source, destination)

    with patch("capability.index.os.replace", side_effect=replace_with_target_failure):
        with pytest.raises(OSError, match="simulated replace failure"):
            save_index(second, target)

    assert target.read_bytes() == before
    loaded = load_index(target)
    assert loaded is not None
    assert loaded.index_version == "first"


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
