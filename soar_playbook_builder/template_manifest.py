"""Air-gap template projection manifest — packaged metadata for all vetted templates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from builder_helpers import SCAFFOLDS, scaffold_pattern
from coa_builder import build_modern_playbook_json
from pattern_catalog import PATTERN_CATALOG, catalog_by_id, pattern_meta
from runtime_fixtures import RUNTIME_FIXTURES

MANIFEST_SCHEMA = "soar_playbook_builder.template_manifest.v1"
PROJECTION_VERSION = "2.11.0"


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def build_template_manifest(*, app_version: str | None = None) -> dict[str, Any]:
    """Build manifest suitable for air-gapped installs and Splunk MCP-style registration hints."""
    templates: list[dict[str, Any]] = []
    for row in PATTERN_CATALOG:
        pid = row["id"]
        meta = pattern_meta(pid)
        scaffold = scaffold_pattern(pid)
        source = scaffold.get("source") or SCAFFOLDS.get(pid, "")
        coa: dict[str, Any] | None = None
        if source and scaffold.get("status") == "success":
            try:
                coa = build_modern_playbook_json(
                    source,
                    row.get("label") or pid,
                    pattern=pid,
                )
            except Exception:  # noqa: BLE001
                coa = None
        fix = RUNTIME_FIXTURES.get(pid)
        templates.append(
            {
                "id": pid,
                "label": row.get("label"),
                "category": row.get("category"),
                "description": row.get("description"),
                "integrations": row.get("integrations") or [],
                "offline": row.get("offline", True),
                "tier": meta.get("tier", "safe"),
                "requires_confirm": meta.get("requires_confirm", False),
                "destructive_actions": meta.get("destructive_actions") or [],
                "nl_keywords": meta.get("nl_keywords") or [],
                "source_bytes": len(source),
                "source_hash": _source_hash(source) if source else "",
                "coa_node_count": len((coa or {}).get("coa", {}).get("data", {}).get("nodes", {}))
                if coa
                else 0,
                "runtime_fixture": {
                    "tier": fix.tier if fix else "safe",
                    "nl_prompt": fix.nl_prompt if fix else "",
                }
                if fix
                else None,
            }
        )

    return {
        "schema_version": MANIFEST_SCHEMA,
        "projection_version": app_version or PROJECTION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "template_count": len(templates),
        "templates": templates,
        "policy_hints": {
            "default_enablement": {
                "safe": True,
                "integration": True,
                "destructive": False,
            },
            "requires_destructive_confirm": True,
        },
    }


def manifest_json(*, app_version: str | None = None, indent: int = 2) -> str:
    return json.dumps(build_template_manifest(app_version=app_version), indent=indent)
