"""Offline documentation-link checker tests."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_docs import check_docs  # noqa: E402


def test_repository_markdown_links_resolve():
    root = Path(__file__).resolve().parents[1]
    assert check_docs(root) == []


def test_missing_and_escaping_links_are_reported(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text(
        "[missing](missing.md)\n[escape](../../outside.md)\n",
        encoding="utf-8",
    )
    errors = check_docs(tmp_path)
    assert any("missing local link" in item for item in errors)
    assert any("escapes repository" in item for item in errors)
