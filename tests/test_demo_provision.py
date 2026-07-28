"""Demo case provisioning helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from demo_provision import (  # noqa: E402
    provision_demo_case,
    resolve_fixture_pattern,
)


def test_resolve_fixture_pattern_from_sample_id():
    assert resolve_fixture_pattern(sample_id=9001) == "failed-logins-okta"
    assert resolve_fixture_pattern(sample_id=9002) == "phishing-enrichment"
    assert resolve_fixture_pattern(sample_id=9003) == "insider-threat-ad"
    assert resolve_fixture_pattern(sample_id=9004) == "es-notable-response"
    assert resolve_fixture_pattern(sample_id=9005) == "hello"


def test_resolve_fixture_pattern_explicit():
    assert resolve_fixture_pattern(pattern_id="hello") == "hello"
    assert resolve_fixture_pattern(pattern_id="unknown-pattern") is None


def test_provision_demo_case_needs_confirm():
    out = provision_demo_case(object(), sample_id=9001)
    assert out["status"] == "success"
    assert out["needs_confirm"] is True
    assert out["pattern_id"] == "failed-logins-okta"


@patch("demo_provision.phantom_rest_call")
def test_provision_demo_case_creates_container(mock_rest):
    mock_rest.side_effect = [
        (True, {"id": 4242}),
        (True, {"id": 1}),
        (True, {"id": 2}),
    ]
    out = provision_demo_case(object(), sample_id=9001, confirm=True)
    assert out["status"] == "success"
    assert out["container_id"] == 4242
    assert out["pattern_id"] == "failed-logins-okta"
    assert mock_rest.call_count >= 1
    first_call = mock_rest.call_args_list[0]
    assert first_call[0][0] == "POST"
    assert first_call[0][1] == "container"
