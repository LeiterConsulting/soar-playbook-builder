#!/usr/bin/env python3
"""Package utility playbooks shipped with SOAR Playbook Builder."""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT.parent / "dist"

PLAYBOOKS = {
    "open_playbook_builder": {
        "name": "Open Playbook Builder",
        "description": (
            "Utility — opens the Playbook Builder sidecar linked to this case. "
            "Adds a case note with the URL from get sidecar url."
        ),
        "labels": ["open_playbook_builder", "playbook_builder"],
        "category": "utilities",
        "tags": ["utility", "playbook_builder", "sidecar"],
    },
}


def package_one(slug: str, meta: dict, py_path: Path, out_path: Path) -> Path:
    py_text = py_path.read_text(encoding="utf-8")
    playbook_json = {
        "name": meta["name"],
        "description": meta["description"],
        "labels": meta["labels"],
        "active": True,
        "draft": False,
        "disabled": False,
        "playbook_type": "automation",
        "python_version": "3",
        "python_version_py": "3",
        "category": meta.get("category", "utilities"),
        "tags": meta.get("tags", []),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_path, "w:gz") as tar:
        for name, data in (
            (f"{slug}/{slug}.py", py_text.encode("utf-8")),
            (f"{slug}/{slug}.json", json.dumps(playbook_json, indent=2).encode("utf-8")),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=BytesIO(data))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Package Playbook Builder utility playbooks")
    parser.add_argument(
        "--slug",
        default="open_playbook_builder",
        choices=list(PLAYBOOKS.keys()),
        help="Which utility playbook to package",
    )
    parser.add_argument("--out-dir", default=str(DIST))
    args = parser.parse_args()

    slug = args.slug
    meta = PLAYBOOKS[slug]
    py_path = ROOT / f"{slug}.py"
    if not py_path.is_file():
        print(f"Missing source: {py_path}", file=sys.stderr)
        return 1
    out_path = Path(args.out_dir) / f"{slug}.tgz"
    package_one(slug, meta, py_path, out_path)
    print(f"Packaged: {out_path} ({out_path.stat().st_size} bytes)")
    print(f"Import: SOAR → Playbooks → Import → {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
