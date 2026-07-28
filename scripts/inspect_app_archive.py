#!/usr/bin/env python3
"""Fail-closed structural and metadata inspection for a SOAR app archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_ROOT = "soar_playbook_builder"
MANIFEST_PATH = f"{EXPECTED_ROOT}/soar_playbook_builder.json"
REQUIRED_FILES = frozenset(
    {
        MANIFEST_PATH,
        f"{EXPECTED_ROOT}/LICENSE",
        f"{EXPECTED_ROOT}/ATTRIBUTION.md",
        (
            f"{EXPECTED_ROOT}/THIRD_PARTY_LICENSES/"
            "react-MIT.txt"
        ),
        (
            f"{EXPECTED_ROOT}/THIRD_PARTY_LICENSES/"
            "react-dom-MIT.txt"
        ),
        (
            f"{EXPECTED_ROOT}/THIRD_PARTY_LICENSES/"
            "highlight.js-BSD-3-Clause.txt"
        ),
    }
)
MAX_MEMBERS = 5_000
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
FORBIDDEN_PARTS = {
    ".DS_Store",
    ".env",
    ".git",
    ".index",
    "__pycache__",
    "node_modules",
}
FORBIDDEN_SUFFIXES = {".key", ".p12", ".pfx"}
FORBIDDEN_FILENAMES = {
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
}


def _validate_member_name(name: str) -> list[str]:
    errors: list[str] = []
    if not name or name.startswith("/") or "\\" in name:
        errors.append(f"unsafe member path: {name!r}")
        return errors
    raw_parts = name.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        errors.append(f"unsafe member path: {name!r}")
        return errors
    path = PurePosixPath(name)
    if path.parts[0] != EXPECTED_ROOT:
        errors.append(f"unexpected archive root: {name!r}")
    lowered = {part.lower() for part in path.parts}
    if lowered & {part.lower() for part in FORBIDDEN_PARTS}:
        errors.append(f"forbidden packaged path: {name!r}")
    filename = path.name.lower()
    if filename.startswith("._"):
        errors.append(f"AppleDouble file is not allowed: {name!r}")
    if filename in FORBIDDEN_FILENAMES:
        errors.append(f"credential-shaped file is not allowed: {name!r}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"private-key container is not allowed: {name!r}")
    return errors


def inspect_archive(path: Path) -> dict[str, Any]:
    """Return inspection evidence; callers fail when ``errors`` is non-empty."""
    path = path.resolve()
    errors: list[str] = []
    names: set[str] = set()
    total_size = 0
    manifest: dict[str, Any] | None = None
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                errors.append(
                    f"archive exceeds {MAX_MEMBERS} members"
                )
            for member in members:
                errors.extend(_validate_member_name(member.name))
                if member.name in names:
                    errors.append(f"duplicate archive member: {member.name}")
                names.add(member.name)
                if member.issym() or member.islnk():
                    errors.append(
                        f"links are not allowed: {member.name}"
                    )
                elif not (member.isdir() or member.isfile()):
                    errors.append(
                        f"special archive entry is not allowed: {member.name}"
                    )
                if member.mode & 0o022:
                    errors.append(
                        f"group/world-writable mode is not allowed: "
                        f"{member.name}"
                    )
                if member.isfile():
                    total_size += member.size
            if total_size > MAX_UNPACKED_BYTES:
                errors.append(
                    "archive uncompressed content exceeds "
                    f"{MAX_UNPACKED_BYTES} bytes"
                )
            for required in sorted(REQUIRED_FILES - names):
                errors.append(f"missing required packaged file: {required}")
            manifest_member = archive.getmember(MANIFEST_PATH)
            if not manifest_member.isfile():
                errors.append("app manifest is not a regular file")
            elif manifest_member.size > MAX_MANIFEST_BYTES:
                errors.append("app manifest is too large")
            else:
                extracted = archive.extractfile(manifest_member)
                raw = extracted.read() if extracted else b""
                manifest = json.loads(raw.decode("utf-8"))
    except KeyError:
        errors.append(f"missing app manifest: {MANIFEST_PATH}")
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        tarfile.TarError,
    ) as exc:
        errors.append(f"archive could not be inspected: {exc}")

    if manifest is not None:
        if not isinstance(manifest, dict):
            errors.append("app manifest must be a JSON object")
        else:
            if manifest.get("package_name") != EXPECTED_ROOT:
                errors.append("manifest package_name does not match root")
            for field in (
                "appid",
                "app_version",
                "min_phantom_version",
                "python_version",
            ):
                if not str(manifest.get(field) or "").strip():
                    errors.append(f"manifest field is missing: {field}")

    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    return {
        "status": "ok" if not errors else "blocked",
        "archive": path.name,
        "sha256": digest,
        "member_count": len(names),
        "unpacked_bytes": total_size,
        "manifest_app_version": (
            manifest.get("app_version")
            if isinstance(manifest, dict)
            else None
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    report = inspect_archive(args.archive)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
