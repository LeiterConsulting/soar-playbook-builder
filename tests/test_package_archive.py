"""Reproducible and fail-closed package archive tests."""

from __future__ import annotations

import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_app_archive import build_archive  # noqa: E402
from inspect_app_archive import inspect_archive  # noqa: E402


def _manifest() -> dict[str, str]:
    return {
        "appid": "00000000-0000-0000-0000-000000000000",
        "app_version": "1.0.0",
        "min_phantom_version": "8.5.0",
        "package_name": "soar_playbook_builder",
        "python_version": "3.13",
    }


def _sample_app(tmp_path: Path) -> Path:
    app = tmp_path / "soar_playbook_builder"
    app.mkdir()
    (app / "soar_playbook_builder.json").write_text(
        json.dumps(_manifest()),
        encoding="utf-8",
    )
    (app / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (app / "docs").mkdir()
    (app / "docs" / "README.md").write_text("hello\n", encoding="utf-8")
    (app / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (app / "ATTRIBUTION.md").write_text(
        "attribution\n",
        encoding="utf-8",
    )
    licenses = app / "THIRD_PARTY_LICENSES"
    licenses.mkdir()
    for name in (
        "react-MIT.txt",
        "react-dom-MIT.txt",
        "highlight.js-BSD-3-Clause.txt",
    ):
        (licenses / name).write_text("license\n", encoding="utf-8")
    return app


def test_archive_is_byte_reproducible_and_inspectable(tmp_path):
    app = _sample_app(tmp_path)
    first = tmp_path / "first.tgz"
    second = tmp_path / "second.tgz"

    build_archive(app, first)
    os.utime(app / "module.py", (2_000_000_000, 2_000_000_000))
    build_archive(app, second)

    assert first.read_bytes() == second.read_bytes()
    report = inspect_archive(first)
    assert report["status"] == "ok"
    assert report["manifest_app_version"] == "1.0.0"


def test_builder_rejects_symbolic_links(tmp_path):
    app = _sample_app(tmp_path)
    target = app / "module.py"
    link = app / "linked.py"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("symbolic links are unavailable")

    with pytest.raises(ValueError, match="symbolic links"):
        build_archive(app, tmp_path / "bad.tgz")


def test_inspector_rejects_traversal_and_link_entries(tmp_path):
    archive_path = tmp_path / "hostile.tgz"
    with tarfile.open(archive_path, "w:gz") as archive:
        manifest_bytes = json.dumps(_manifest()).encode("utf-8")
        manifest = tarfile.TarInfo(
            "soar_playbook_builder/soar_playbook_builder.json"
        )
        manifest.size = len(manifest_bytes)
        manifest.mode = 0o644
        archive.addfile(manifest, io.BytesIO(manifest_bytes))

        traversal = tarfile.TarInfo("../outside")
        traversal.size = 1
        traversal.mode = 0o644
        archive.addfile(traversal, io.BytesIO(b"x"))

        link = tarfile.TarInfo("soar_playbook_builder/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        link.mode = 0o777
        archive.addfile(link)

    report = inspect_archive(archive_path)
    assert report["status"] == "blocked"
    assert any("unsafe member path" in item for item in report["errors"])
    assert any("links are not allowed" in item for item in report["errors"])
