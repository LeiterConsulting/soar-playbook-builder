#!/usr/bin/env python3
"""Build a byte-reproducible SOAR app archive from a staged directory."""

from __future__ import annotations

import argparse
import gzip
import os
import tarfile
import tempfile
from pathlib import Path

EXCLUDED_NAMES = {
    ".DS_Store",
    ".env",
    ".git",
    ".index",
    "__pycache__",
    "node_modules",
}


def _is_excluded(relative: Path) -> bool:
    return any(
        part in EXCLUDED_NAMES or part.startswith("._")
        for part in relative.parts
    )


def _archive_name(app_name: str, relative: Path) -> str:
    if not relative.parts:
        return app_name
    return f"{app_name}/{relative.as_posix()}"


def _tar_info(path: Path, archive_name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
    elif path.is_file():
        info.type = tarfile.REGTYPE
        info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
        info.size = path.stat().st_size
    else:
        raise ValueError(f"unsupported archive entry: {path}")
    return info


def build_archive(app_dir: Path, output: Path) -> str:
    """Create a deterministic gzip-compressed USTAR archive."""
    app_dir = app_dir.resolve()
    output = output.resolve()
    if not app_dir.is_dir():
        raise ValueError(f"app directory does not exist: {app_dir}")
    if app_dir.name != "soar_playbook_builder":
        raise ValueError(
            "app directory must be named 'soar_playbook_builder'"
        )

    entries = [app_dir]
    for path in app_dir.rglob("*"):
        relative = path.relative_to(app_dir)
        if _is_excluded(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed: {relative}")
        entries.append(path)
    entries.sort(
        key=lambda path: _archive_name(
            app_dir.name,
            path.relative_to(app_dir),
        )
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                compresslevel=9,
                mtime=0,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.USTAR_FORMAT,
                ) as archive:
                    for path in entries:
                        relative = path.relative_to(app_dir)
                        archive_name = _archive_name(
                            app_dir.name,
                            relative,
                        )
                        info = _tar_info(path, archive_name)
                        if path.is_file():
                            with path.open("rb") as source:
                                archive.addfile(info, source)
                        else:
                            archive.addfile(info)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        name = build_archive(args.app_dir, args.output)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.error(str(exc))
    print(f"Built {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
