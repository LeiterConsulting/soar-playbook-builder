"""Tests for case catalog."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from case_catalog import (  # noqa: E402
    DEFAULT_SAMPLE_CASES,
    list_cases_payload,
    lookup_sample_case,
    parse_sample_cases_json,
)


class _Req:
    GET = {}


def test_parse_sample_cases_json():
    raw = '[{"id": 1, "name": "Test", "severity": "low"}]'
    cases = parse_sample_cases_json(raw)
    assert len(cases) == 1
    assert cases[0]["source"] == "sample"


def test_lookup_sample_case():
    row = lookup_sample_case(9001)
    assert row is not None
    assert row["name"].startswith("Failed Logins")
    assert lookup_sample_case(9005)["fixture_pattern_id"] == "hello"
    assert lookup_sample_case(9004)["showcase_recommended"] is True


def test_showcase_sample_ids():
    payload = list_cases_payload(_Req(), sample_cases_json=None, enrich_artifacts=False)
    assert 9002 in payload["showcase_sample_ids"]
    assert 9005 in payload["showcase_sample_ids"]


def test_list_cases_includes_samples_without_soar():
    payload = list_cases_payload(_Req(), sample_cases_json=None, enrich_artifacts=False)
    assert payload["status"] == "success"
    assert payload["sample_count"] == len(DEFAULT_SAMPLE_CASES)
    assert len(payload["cases"]) >= len(DEFAULT_SAMPLE_CASES)


if __name__ == "__main__":
    test_parse_sample_cases_json()
    test_lookup_sample_case()
    test_list_cases_includes_samples_without_soar()
    print("ok")
