"""Tests for coach case intel (L1 read-only)."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from coach_case_intel import coach_case_intel  # noqa: E402


def test_coach_case_intel_no_container():
    out = coach_case_intel(None)
    assert out["run_count"] == 0
    assert out["recent_runs"] == []


def test_coach_case_intel_with_runs():
    fake_runs = [
        {"id": 1, "playbook_id": 42, "status": "success", "name": "Test PB"},
    ]
    with patch("coach_case_intel.fetch_container_playbook_runs", return_value=fake_runs):
        out = coach_case_intel(9001)
    assert out["run_count"] == 1
    assert out["recent_runs"][0]["name"] == "Test PB"


if __name__ == "__main__":
    test_coach_case_intel_no_container()
    test_coach_case_intel_with_runs()
    print("ok")
