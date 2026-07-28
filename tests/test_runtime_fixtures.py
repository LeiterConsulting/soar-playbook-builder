"""Runtime fixture coverage for every catalog template."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from pattern_catalog import catalog_ids  # noqa: E402
from runtime_fixtures import RUNTIME_FIXTURES  # noqa: E402


def test_every_catalog_pattern_has_fixture():
    missing = [pid for pid in catalog_ids() if pid not in RUNTIME_FIXTURES]
    assert not missing, f"Missing runtime fixtures: {missing}"


def test_fixture_ids_match_catalog():
    extra = [pid for pid in RUNTIME_FIXTURES if pid not in catalog_ids()]
    assert not extra, f"Fixtures without catalog entry: {extra}"
