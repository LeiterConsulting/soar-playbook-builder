"""Tests for context-safe static HTML template rendering."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from html_template import render_html_template  # noqa: E402


def test_render_html_template_escapes_text_and_attribute_breakout(tmp_path: Path):
    (tmp_path / "shell.html").write_text(
        '<div data-value="{{VALUE}}">{{VALUE}}</div>',
        encoding="utf-8",
    )
    hostile = '"><img src=x onerror=alert(1)><script>alert(2)</script>'

    rendered = render_html_template(tmp_path, "shell.html", {"VALUE": hostile})

    assert hostile not in rendered
    assert "<script>" not in rendered
    assert "<img" not in rendered
    assert "&quot;&gt;&lt;img" in rendered


def test_render_html_template_rejects_path_traversal(tmp_path: Path):
    try:
        render_html_template(tmp_path, "../shell.html", {})
    except ValueError as exc:
        assert "local .html filename" in str(exc)
    else:
        raise AssertionError("path traversal template name was accepted")


def test_render_html_template_missing_file_is_safe(tmp_path: Path):
    rendered = render_html_template(tmp_path, "missing.html", {})
    assert rendered == "<html><body>Missing template: missing.html</body></html>"
