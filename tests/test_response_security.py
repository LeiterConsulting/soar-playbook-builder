"""Tests for response security headers and CSP-compatible templates."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from response_security import apply_security_headers  # noqa: E402


def test_html_headers_allow_only_same_origin_resources_and_framing():
    response = {}
    assert apply_security_headers(response, html_document=True) is response
    assert response["Cache-Control"] == "no-store, max-age=0"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    assert "script-src 'self'" in response["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" not in response["Content-Security-Policy"]
    assert "style-src 'self' 'unsafe-inline'" in response["Content-Security-Policy"]


def test_api_headers_deny_document_embedding():
    response = {}
    apply_security_headers(response)
    assert response["X-Frame-Options"] == "DENY"
    assert response["Content-Security-Policy"].startswith("default-src 'none'")
    assert response["Referrer-Policy"] == "no-referrer"


def test_widget_templates_do_not_require_inline_script_or_style():
    widget_dir = ROOT / "widgets"
    for name in ("agent_chat.html", "playbook_builder_widget.html"):
        template = (widget_dir / name).read_text(encoding="utf-8").lower()
        assert "<script>" not in template
        assert "<style>" not in template
        assert "onclick=" not in template
