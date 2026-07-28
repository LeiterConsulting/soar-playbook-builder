"""Tests for draft import packaging."""

import base64
import io
import json
import sys
import tarfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from draft_import import (
    DEFAULT_PLAYBOOK_PYTHON_VERSION,
    _import_api_succeeded,
    _normalize_playbook_source_for_import,
    _record_matches_import,
    build_playbook_metadata,
    is_legacy_python27,
    is_python_39,
    import_nl_draft,
    package_source_flat_py_b64,
    package_source_with_metadata_b64,
    slug_from_label,
)


def test_import_api_succeeded_rejects_failed():
    assert not _import_api_succeeded({"failed": True, "message": "bad tarball"})
    assert _import_api_succeeded({"success": True, "id": 5})


def test_slug_from_label():
    assert slug_from_label("Palo Alto Block IP") == "palo_alto_block_ip"


def test_record_matches_import_by_slug():
    assert _record_matches_import({"name": "hello_world"}, "Hello World", "hello_world")
    assert _record_matches_import(
        {"name": "hello_world/hello_world"}, "Hello World", "hello_world"
    )
    assert not _record_matches_import({"name": "other_playbook"}, "Hello World", "hello_world")


def test_package_source_with_metadata_b64_root_files():
    source = "import phantom.app as phantom\n\ndef on_start(container):\n    pass\n"
    meta = build_playbook_metadata("Test Playbook", pattern="hello")
    slug = slug_from_label("Test Playbook")
    b64 = package_source_with_metadata_b64(source, slug, meta)
    raw = base64.b64decode(b64)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = tar.getnames()
    assert f"{slug}.py" in names
    assert f"{slug}.json" in names
    assert f"{slug}/{slug}.py" not in names
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        loaded = json.loads(tar.extractfile(f"{slug}.json").read().decode("utf-8"))
    assert loaded["name"] == "Test Playbook"
    assert loaded["python_version"] == DEFAULT_PLAYBOOK_PYTHON_VERSION
    assert "playbook_builder" in loaded["labels"]


def test_normalize_playbook_source_adds_pylint_disable():
    src = "import phantom.app as phantom\n\ndef on_start(container):\n    pass\n"
    out = _normalize_playbook_source_for_import(src)
    assert out.startswith("# pylint: disable=no-member")
    assert "import phantom.app as phantom" in out


def test_python_version_helpers():
    assert is_python_39({"python_version": "3.9"})
    assert is_python_39({"python_version": "3"})
    assert not is_python_39({"python_version": "2.7"})
    assert is_legacy_python27({"python_version": "2.7"})
    assert is_legacy_python27({})
    assert not is_legacy_python27({"python_version": "3.9"})


def test_package_flat_py_only():
    slug = "hello_world"
    b64 = package_source_flat_py_b64("pass", slug)
    raw = base64.b64decode(b64)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        assert tar.getnames() == ["hello_world.py"]


def test_import_never_deletes_or_overwrites_legacy_python_playbook():
    source = (
        "import phantom.app as phantom\n\n"
        "def on_start(container):\n"
        "    phantom.debug('hello')\n"
    )
    with patch(
        "draft_import.find_playbook_by_slug",
        return_value={
            "id": 41,
            "name": "hello_world",
            "python_version": "2.7",
        },
    ):
        with patch("draft_import.import_playbook_b64") as upload:
            result = import_nl_draft(
                source,
                name="Hello World",
                request=None,
                skip_asset_check=True,
            )
    assert result["status"] == "error"
    assert (
        result["error_code"]
        == "LEGACY_PYTHON_PLAYBOOK_UNSUPPORTED"
    )
    upload.assert_not_called()
