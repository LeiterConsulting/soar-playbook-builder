"""Tests for Splunk Enterprise splunk_link redirect."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from sidecar_url import build_sidecar_query_params  # noqa: E402
from splunk_link import resolve_splunk_link_params, splunk_link_redirect_url  # noqa: E402


def test_resolve_splunk_link_params():
    param = resolve_splunk_link_params(
        sid="1234567890.1",
        rule_name="Suspicious login",
        src="10.0.0.5",
        mode="coach",
        tab="respond",
    )
    assert param["mode"] == "coach"
    assert param["tab"] == "respond"
    assert param["rule_name"] == "Suspicious login"
    assert "sid=" in param.get("investigation_id", "")


def test_splunk_link_url():
    url = splunk_link_redirect_url(
        "https://soar/rest/handler/dir/asset",
        rule_name="Test",
        container_id=99,
        mode="assistant",
    )
    assert "container_id=99" in url
    assert "mode=assistant" in url


def test_build_sidecar_query_includes_splunk_fields():
    pairs = build_sidecar_query_params({"mode": "coach", "investigation_id": "sid=abc"})
    assert ("mode", "coach") in pairs


if __name__ == "__main__":
    test_resolve_splunk_link_params()
    test_splunk_link_url()
    test_build_sidecar_query_includes_splunk_fields()
    print("ok")
