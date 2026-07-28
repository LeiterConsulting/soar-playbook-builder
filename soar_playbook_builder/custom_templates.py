"""Organization-specific playbook templates from Playbook Builder asset config."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

from builder_helpers import analyze_playbook

from pattern_catalog import PATTERN_CATALOG, catalog_by_id as shipped_catalog_by_id

ORG_ID_RE = re.compile(r"^org-[a-z][a-z0-9-]{2,48}$")
VALID_TIERS = frozenset({"safe", "integration", "destructive"})
SHIPPED_IDS = frozenset(row["id"] for row in PATTERN_CATALOG)


@dataclass
class OrgTemplateRegistry:
    """Parsed org templates ready to merge with the shipped catalog."""

    catalog_rows: list[dict[str, Any]] = field(default_factory=list)
    scaffolds: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    nl_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    destructive_actions: dict[str, list[str]] = field(default_factory=dict)
    tiers: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.catalog_rows)

    def scaffold_source(self, pattern_id: str) -> str | None:
        return self.scaffolds.get(pattern_id)

    def label_for(self, pattern_id: str) -> str | None:
        return self.labels.get(pattern_id)


def _parse_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"__parse_error__": str(exc)}
    return data if isinstance(data, dict) else None


def _validate_source(source: str) -> tuple[bool, str | None]:
    if "def on_start" not in source:
        return False, "source must define on_start(container)"
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, f"invalid Python: {exc.msg}"
    return True, None


def parse_org_templates(raw_config: Any) -> OrgTemplateRegistry:
    """Load org templates from asset `custom_templates_json`."""
    registry = OrgTemplateRegistry()
    data = _parse_json(raw_config)
    if data is None:
        return registry
    if "__parse_error__" in data:
        registry.errors.append(f"custom_templates_json is not valid JSON: {data['__parse_error__']}")
        return registry

    templates = data.get("templates")
    if templates is None:
        return registry
    if not isinstance(templates, list):
        registry.errors.append('"templates" must be a JSON array')
        return registry

    seen: set[str] = set()
    for idx, row in enumerate(templates):
        prefix = f"templates[{idx}]"
        if not isinstance(row, dict):
            registry.errors.append(f"{prefix}: must be an object")
            continue

        tid = str(row.get("id") or "").strip().lower().replace("_", "-")
        if not tid:
            registry.errors.append(f"{prefix}: missing id")
            continue
        if not ORG_ID_RE.match(tid):
            registry.errors.append(
                f"{prefix}: id {tid!r} must match org-<name> (e.g. org-crowdstrike-isolate)"
            )
            continue
        if tid in SHIPPED_IDS:
            registry.errors.append(f"{prefix}: id {tid!r} conflicts with a shipped template")
            continue
        if tid in seen:
            registry.errors.append(f"{prefix}: duplicate id {tid!r}")
            continue
        seen.add(tid)

        source = str(row.get("source") or "").strip()
        if not source:
            registry.errors.append(f"{prefix}: missing source")
            continue
        ok, err = _validate_source(source)
        if not ok:
            registry.errors.append(f"{prefix}: {err}")
            continue

        analysis = analyze_playbook(source)
        if analysis.get("score", 0) < 40:
            registry.warnings.append(
                f"{prefix}: low validation score ({analysis.get('score')}/100) — template still loaded"
            )

        tier = str(row.get("tier") or "integration").lower()
        if tier not in VALID_TIERS:
            registry.errors.append(f"{prefix}: tier must be safe, integration, or destructive")
            continue

        label = str(row.get("label") or tid.replace("org-", "").replace("-", " ").title())
        category = str(row.get("category") or "Organization")
        description = str(row.get("description") or f"Organization template ({tid})")
        integrations = row.get("integrations") if isinstance(row.get("integrations"), list) else []
        integrations = [str(x) for x in integrations if x]
        destructive = row.get("destructive_actions") if isinstance(row.get("destructive_actions"), list) else []
        destructive = [str(x) for x in destructive if x]

        kw_raw = row.get("nl_keywords") if isinstance(row.get("nl_keywords"), list) else []
        nl_keywords = tuple(str(k).lower() for k in kw_raw if k)

        catalog_row = {
            "id": tid,
            "label": label,
            "category": category,
            "description": description,
            "integrations": integrations,
            "offline": True,
            "org": True,
            "tier": tier,
            "requires_confirm": tier == "destructive",
            "destructive_actions": destructive,
            "nl_keywords": list(nl_keywords),
        }
        registry.catalog_rows.append(catalog_row)
        registry.scaffolds[tid] = source
        registry.labels[tid] = label
        registry.tiers[tid] = tier
        if destructive:
            registry.destructive_actions[tid] = destructive
        if nl_keywords:
            registry.nl_keywords[tid] = nl_keywords

    return registry


def merged_catalog_by_id(org: OrgTemplateRegistry | None = None) -> dict[str, dict[str, Any]]:
    merged = shipped_catalog_by_id()
    if org:
        for row in org.catalog_rows:
            merged[row["id"]] = row
    return merged
