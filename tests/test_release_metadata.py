"""Release metadata, supply-chain, and documentation drift tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT / "soar_playbook_builder" / "soar_playbook_builder.json"
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_app_ui_lock_and_changelog_versions_match():
    manifest_version = _json(MANIFEST_PATH)["app_version"]
    ui_package = _json(ROOT / "sidecar-ui" / "package.json")
    ui_lock = _json(ROOT / "sidecar-ui" / "package-lock.json")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert ui_package["version"] == manifest_version
    assert ui_lock["version"] == manifest_version
    assert (
        ui_lock["packages"][""]["version"]
        == manifest_version
    )
    assert f"## [{manifest_version}]" in changelog
    assert f"version-{manifest_version}-" in readme


def test_license_and_configuration_order_are_consistent():
    manifest = _json(MANIFEST_PATH)
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    attribution = (ROOT / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert manifest["license"] == "MIT"
    assert license_text.startswith("MIT License")
    assert "MIT" in attribution

    orders = [
        definition["order"]
        for definition in manifest["configuration"].values()
    ]
    assert orders == list(range(len(orders)))


def test_github_actions_are_sha_pinned_and_use_node_24():
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflow_paths
    uses_pattern = re.compile(
        r"^\s*uses:\s*[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$",
        re.MULTILINE,
    )
    for path in workflow_paths:
        text = path.read_text(encoding="utf-8")
        uses_lines = [
            line for line in text.splitlines() if "uses:" in line
        ]
        assert uses_lines
        assert len(uses_pattern.findall(text)) == len(uses_lines)
        if "setup-node" in text:
            assert 'node-version: "24"' in text


def test_dependency_constraints_and_node_engines_are_bounded():
    assert (
        ROOT / ".nvmrc"
    ).read_text(encoding="utf-8").strip() == "24"
    for project in ("sidecar-ui", "validation-console"):
        package = _json(ROOT / project / "package.json")
        assert package["engines"]["node"] == ">=24 <27"
    for requirements in (
        ROOT / "requirements.txt",
        ROOT / "scripts" / "requirements-validate.txt",
    ):
        lines = [
            line.strip()
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines
        assert all("==" in line for line in lines)


def test_offline_security_docs_exist():
    for relative in (
        "SECURITY.md",
        "docs/OFFLINE_FOUNDATION_IMPLEMENTATION.md",
        "docs/OFFLINE_READINESS.md",
        "docs/THREAT_MODEL.md",
        "docs/TRUSTED_RELEASE_PLAN.md",
        "docs/TRUSTED_REVIEW.md",
    ):
        assert (ROOT / relative).is_file()
    bundled_source_docs = ROOT / "soar_playbook_builder" / "docs"
    assert not bundled_source_docs.exists() or not any(
        bundled_source_docs.iterdir()
    )
