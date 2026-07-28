#!/usr/bin/env python3
"""Emit dist/template-manifest.json for air-gapped template projection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "soar_playbook_builder"))

from template_manifest import build_template_manifest, manifest_json  # noqa: E402


def main() -> int:
    out_dir = ROOT / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "template-manifest.json"
    out_path.write_text(manifest_json(), encoding="utf-8")
    manifest = build_template_manifest()
    print(f"Wrote {out_path} ({manifest['template_count']} templates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
