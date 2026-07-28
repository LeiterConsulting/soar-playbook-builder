"""Tests for coach suggest payload."""

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from coach import coach_suggest_payload  # noqa: E402


class _Req:
    GET = {"rule_name": "Access - Excessive Failed Logins", "container_id": "9001"}
    POST = {}


def test_coach_suggest_sample_case():
    cfg = {"sample_cases_json": ""}
    out = coach_suggest_payload(_Req(), cfg, {})
    assert out["status"] == "success"
    assert out.get("suggested_pattern") == "failed-logins-okta"
    assert "failed-logins-okta" in (out.get("content") or "")
    assert out.get("coach_lane") == "respond"


if __name__ == "__main__":
    test_coach_suggest_sample_case()
    print("ok")
