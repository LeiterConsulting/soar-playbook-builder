#!/usr/bin/env python3
"""One-shot content pass: remove NNSA branding from lab kit and related paths."""

from __future__ import annotations

import os
import re
from pathlib import Path

# Text replacements (longer phrases first)
REPLACEMENTS: list[tuple[str, str]] = [
    ("es_nnsa_response", "es_notable_response"),
    ("NNSA ES Premier Lab", "ES Premier Lab"),
    ("NNSA on-prem", "on-prem"),
    ("NNSA offline", "air-gapped"),
    ("NNSA Lab", "ES Premier Lab"),
    ("NNSA lab", "ES Premier lab"),
    ("NNSA playbook", "ES Premier lab playbook"),
    ("NNSA POV", "ES Premier POV"),
    ("NNSA POV kit", "ES Premier POV kit"),
    ("NNSA demo", "lab demo"),
    ("NNSA deploy", "production deploy"),
    ("NNSA environments", "on-prem environments"),
    ("NNSA environment", "on-prem environment"),
    ("NNSA audiences", "on-prem audiences"),
    ("NNSA showcase", "ES Premier showcase"),
    ("NNSA correlation", "ES Premier lab correlation"),
    ("NNSA Failed Logins", "Excessive Failed Logins"),
    ("NNSA quick start", "Failed logins quick start"),
    ("NNSA_QUICK_START.md", "FAILED_LOGINS_QUICK_START.md"),
    ("NNSA_LAB_PATH", "ES_PREMIER_LAB_PATH"),
    ("NNSA_PLAYBOOK_TGZ", "ES_PREMIER_PLAYBOOK_TGZ"),
    ("~/Downloads/nnsa_es_premier_lab", "~/Downloads/es_premier_lab"),
    ("nnsa_es_premier_lab", "es_premier_lab"),
    ("nnsa_es_pov", "es_premier_pov"),
    ("nnsa_lab_console", "es_premier_lab_console"),
    ("nnsa_lab_scenario", "es_premier_lab_scenario"),
    ("nnsa_ueba_risk_view", "es_premier_ueba_risk_view"),
    ("nnsa_agent_sidecar", "es_premier_agent_sidecar"),
    ("nnsa_identity_enrichment", "es_premier_identity_enrichment"),
    ("savedsearches_nnsa_lab", "savedsearches_es_premier_lab"),
    ("transforms_nnsa_lab", "transforms_es_premier_lab"),
    ("nnsa_failed_logins", "excessive_failed_logins"),
    ("import_nnsa_playbook", "import_es_premier_playbook"),
    ("NNSA Failed Logins (Okta)", "Excessive Failed Logins (Okta)"),
    ("NNSA Failed Logins → Okta", "Excessive Failed Logins → Okta"),
    ("- NNSA Lab", "- ES Premier Lab"),
    ("NNSA Adaptations", "On-prem adaptations"),
    ("NNSA On-Prem", "On-Prem"),
    (" (NNSA)", ""),
    ("NNSA ", ""),
]

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "eventgen/drop",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pptx", ".odp", ".zip", ".tgz", ".pem"}

FILE_RENAMES: list[tuple[str, str]] = [
    ("nnsa_lab_console.xml", "es_premier_lab_console.xml"),
    ("nnsa_lab_scenario.xml", "es_premier_lab_scenario.xml"),
    ("nnsa_ueba_risk_view.xml", "es_premier_ueba_risk_view.xml"),
    ("nnsa_agent_sidecar.xml", "es_premier_agent_sidecar.xml"),
    ("savedsearches_nnsa_lab.conf", "savedsearches_es_premier_lab.conf"),
    ("transforms_nnsa_lab.conf", "transforms_es_premier_lab.conf"),
    ("nnsa_identity_enrichment.csv", "es_premier_identity_enrichment.csv"),
    ("nnsa_cisco_se_process_creation.conf.stub", "cisco_se_process_creation.conf.stub"),
]


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if path.name.startswith("._"):
        return True
    return False


def apply_replacements(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    # NL keyword cleanup — remove bare "nnsa" token in keyword tuples
    text = re.sub(r'"nnsa",\s*', "", text)
    text = re.sub(r",\s*\"nnsa\"", "", text)
    text = re.sub(r'\("nnsa"\)', "()", text)
    return text


def process_file(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    updated = apply_replacements(raw)
    if updated != raw:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def rename_files(root: Path) -> int:
    count = 0
    for old_name, new_name in FILE_RENAMES:
        for path in root.rglob(old_name):
            if should_skip(path):
                continue
            dest = path.with_name(new_name)
            if dest.exists():
                continue
            path.rename(dest)
            count += 1
    # splunk_app folder rename
    legacy_app = root / "splunk_app" / "nnsa_es_premier_lab"
    new_app = root / "splunk_app" / "es_premier_lab"
    if legacy_app.is_dir() and not new_app.exists():
        legacy_app.rename(new_app)
        count += 1
    return count


def main() -> None:
    roots = [
        Path(os.path.expanduser("~/Downloads/es_premier_lab")),
        Path(os.path.expanduser("~/splunk-es-premier-lab")),
        Path(os.path.expanduser("~/mcp-for-splunk/mcp_soar_tutor")),
        Path(os.path.expanduser("~/mcp-for-splunk/packaging/mcp-soar-tutor-server/mcp_soar_tutor")),
        Path(os.path.expanduser("~/.cursor/agents")),
        Path(os.path.expanduser("~/.cursor/skills")),
    ]
    changed = 0
    for root in roots:
        if not root.is_dir():
            print(f"skip missing {root}")
            continue
        if "es_premier_lab" in str(root) and root.name == "es_premier_lab":
            renamed = rename_files(root)
            print(f"{root}: renamed {renamed} paths")
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            if process_file(path):
                changed += 1
    print(f"updated {changed} files")


if __name__ == "__main__":
    main()
