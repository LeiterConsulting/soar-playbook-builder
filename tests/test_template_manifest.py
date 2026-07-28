"""Tests for air-gap template manifest."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from pattern_catalog import catalog_ids  # noqa: E402
from template_manifest import MANIFEST_SCHEMA, build_template_manifest  # noqa: E402


def test_manifest_covers_catalog():
    manifest = build_template_manifest()
    assert manifest["schema_version"] == MANIFEST_SCHEMA
    ids = {t["id"] for t in manifest["templates"]}
    assert ids == set(catalog_ids())


def test_destructive_templates_flagged():
    manifest = build_template_manifest()
    destructive = [t for t in manifest["templates"] if t["tier"] == "destructive"]
    assert len(destructive) >= 4
    for row in destructive:
        assert row["requires_confirm"] is True


if __name__ == "__main__":
    test_manifest_covers_catalog()
    test_destructive_templates_flagged()
    print("ok")
