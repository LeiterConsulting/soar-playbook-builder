"""Organization-specific playbook templates from Playbook Builder asset config."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

from builder_helpers import analyze_playbook
from ir.schema import IRValidationError, PlaybookIR

from pattern_catalog import PATTERN_CATALOG, catalog_by_id as shipped_catalog_by_id

ORG_ID_RE = re.compile(r"^org-[a-z][a-z0-9-]{2,48}$")
VALID_TIERS = frozenset({"safe", "integration", "destructive"})
SHIPPED_IDS = frozenset(row["id"] for row in PATTERN_CATALOG)
MAX_CONFIG_BYTES = 1024 * 1024
MAX_TEMPLATES = 128
MAX_LEGACY_SOURCE_BYTES = 256 * 1024
MAX_LABEL_CHARS = 256
MAX_CATEGORY_CHARS = 128
MAX_DESCRIPTION_CHARS = 4096
MAX_METADATA_ITEMS = 64
MAX_METADATA_ITEM_CHARS = 256
_METADATA_LIST_FIELDS = (
    "integrations",
    "destructive_actions",
    "nl_keywords",
)


@dataclass
class OrgTemplateRegistry:
    """Parsed org templates ready to merge with the shipped catalog."""

    catalog_rows: list[dict[str, Any]] = field(default_factory=list)
    scaffolds: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    nl_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    destructive_actions: dict[str, list[str]] = field(default_factory=dict)
    tiers: dict[str, str] = field(default_factory=dict)
    ir_templates: dict[str, PlaybookIR] = field(default_factory=dict)
    template_kinds: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.catalog_rows)

    def scaffold_source(self, pattern_id: str) -> str | None:
        return self.scaffolds.get(pattern_id)

    def label_for(self, pattern_id: str) -> str | None:
        return self.labels.get(pattern_id)

    def ir_for(self, pattern_id: str) -> PlaybookIR | None:
        return self.ir_templates.get(pattern_id)


def _parse_json(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        try:
            encoded = json.dumps(
                raw,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            return {"__parse_error__": f"not JSON-safe: {exc}"}
        if len(encoded) > MAX_CONFIG_BYTES:
            return {
                "__parse_error__": (
                    f"configuration exceeds {MAX_CONFIG_BYTES} UTF-8 bytes"
                )
            }
        return raw
    if not isinstance(raw, str):
        return {"__parse_error__": "configuration must be a JSON object or string"}
    text = raw.strip()
    if not text:
        return None
    if len(text.encode("utf-8")) > MAX_CONFIG_BYTES:
        return {
            "__parse_error__": (
                f"configuration exceeds {MAX_CONFIG_BYTES} UTF-8 bytes"
            )
        }

    def _reject_duplicate_keys(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key {key!r}")
            obj[key] = value
        return obj

    def _reject_nonfinite(value: str) -> Any:
        raise ValueError(f"non-finite JSON number {value!r}")

    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return {"__parse_error__": str(exc)}
    if not isinstance(data, dict):
        return {"__parse_error__": "top-level JSON value must be an object"}
    return data


def _validate_source(source: str) -> tuple[bool, str | None]:
    if "def on_start" not in source:
        return False, "source must define on_start(container)"
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, f"invalid Python: {exc.msg}"
    return True, None


def _normalized_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip().lower().replace("_", "-")


def _validate_id(
    registry: OrgTemplateRegistry,
    *,
    tid: str,
    prefix: str,
    seen: set[str],
) -> bool:
    if not tid:
        registry.errors.append(f"{prefix}: missing id")
        return False
    if not ORG_ID_RE.match(tid):
        registry.errors.append(
            f"{prefix}: id {tid!r} must match org-<name> "
            "(e.g. org-crowdstrike-isolate)"
        )
        return False
    if tid in SHIPPED_IDS:
        registry.errors.append(
            f"{prefix}: id {tid!r} conflicts with a shipped template"
        )
        return False
    if tid in seen:
        registry.errors.append(f"{prefix}: duplicate id {tid!r}")
        return False
    seen.add(tid)
    return True


def _metadata(
    row: dict[str, Any],
    tid: str,
) -> tuple[str, str, str, list[str], list[str], tuple[str, ...]]:
    tier = str(row.get("tier") or "integration").lower()
    label = str(
        row.get("label")
        or tid.replace("org-", "").replace("-", " ").title()
    )
    category = str(row.get("category") or "Organization")
    description = str(
        row.get("description") or f"Organization template ({tid})"
    )
    integrations = (
        row.get("integrations")
        if isinstance(row.get("integrations"), list)
        else []
    )
    integrations = [str(x) for x in integrations if x]
    destructive = (
        row.get("destructive_actions")
        if isinstance(row.get("destructive_actions"), list)
        else []
    )
    destructive = [str(x) for x in destructive if x]
    kw_raw = (
        row.get("nl_keywords")
        if isinstance(row.get("nl_keywords"), list)
        else []
    )
    nl_keywords = tuple(str(k).lower() for k in kw_raw if k)
    return (
        tier,
        label,
        category,
        integrations,
        destructive,
        nl_keywords,
    )


def _validate_metadata(
    registry: OrgTemplateRegistry,
    *,
    row: dict[str, Any],
    prefix: str,
) -> bool:
    scalar_limits = {
        "label": MAX_LABEL_CHARS,
        "category": MAX_CATEGORY_CHARS,
        "description": MAX_DESCRIPTION_CHARS,
        "tier": 32,
    }
    for field_name, limit in scalar_limits.items():
        value = row.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            registry.errors.append(f"{prefix}: {field_name} must be a string")
            return False
        if len(value) > limit:
            registry.errors.append(
                f"{prefix}: {field_name} exceeds {limit} characters"
            )
            return False
    for field_name in _METADATA_LIST_FIELDS:
        value = row.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            registry.errors.append(f"{prefix}: {field_name} must be an array")
            return False
        if len(value) > MAX_METADATA_ITEMS:
            registry.errors.append(
                f"{prefix}: {field_name} exceeds {MAX_METADATA_ITEMS} items"
            )
            return False
        for item_idx, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                registry.errors.append(
                    f"{prefix}: {field_name}[{item_idx}] must be a "
                    "non-empty string"
                )
                return False
            if len(item) > MAX_METADATA_ITEM_CHARS:
                registry.errors.append(
                    f"{prefix}: {field_name}[{item_idx}] exceeds "
                    f"{MAX_METADATA_ITEM_CHARS} characters"
                )
                return False
    return True


def _add_catalog_row(
    registry: OrgTemplateRegistry,
    *,
    tid: str,
    row: dict[str, Any],
    template_kind: str,
    prefix: str,
) -> bool:
    if not _validate_metadata(registry, row=row, prefix=prefix):
        return False
    tier, label, category, integrations, destructive, nl_keywords = _metadata(
        row,
        tid,
    )
    if tier not in VALID_TIERS:
        registry.errors.append(
            f"{tid}: tier must be safe, integration, or destructive"
        )
        return False
    catalog_row = {
        "id": tid,
        "label": label,
        "category": category,
        "description": str(
            row.get("description") or f"Organization template ({tid})"
        ),
        "integrations": integrations,
        "offline": True,
        "org": True,
        "tier": tier,
        "requires_confirm": tier == "destructive",
        "destructive_actions": destructive,
        "nl_keywords": list(nl_keywords),
        "trusted_ir": template_kind == "ir",
        "template_kind": template_kind,
    }
    registry.catalog_rows.append(catalog_row)
    registry.labels[tid] = label
    registry.tiers[tid] = tier
    registry.template_kinds[tid] = template_kind
    if destructive:
        registry.destructive_actions[tid] = destructive
    if nl_keywords:
        registry.nl_keywords[tid] = nl_keywords
    return True


def parse_org_templates(
    raw_config: Any,
    *,
    raw_ir_config: Any = None,
    allow_legacy_python: bool = False,
) -> OrgTemplateRegistry:
    """Load strict IR templates and optional explicitly-enabled legacy Python."""
    registry = OrgTemplateRegistry()
    seen: set[str] = set()

    ir_data = _parse_json(raw_ir_config)
    if ir_data is not None:
        if "__parse_error__" in ir_data:
            registry.errors.append(
                "custom_ir_templates_json is not valid JSON: "
                f"{ir_data['__parse_error__']}"
            )
        else:
            templates = ir_data.get("templates")
            if templates is not None and not isinstance(templates, list):
                registry.errors.append(
                    'custom_ir_templates_json "templates" must be a JSON array'
                )
            ir_rows = templates if isinstance(templates, list) else []
            if len(ir_rows) > MAX_TEMPLATES:
                registry.errors.append(
                    "custom_ir_templates_json templates exceeds "
                    f"{MAX_TEMPLATES} entries"
                )
                ir_rows = ir_rows[:MAX_TEMPLATES]
            for idx, row in enumerate(ir_rows):
                prefix = f"custom_ir_templates_json.templates[{idx}]"
                if not isinstance(row, dict):
                    registry.errors.append(f"{prefix}: must be an object")
                    continue
                tid = _normalized_id(row)
                if not _validate_id(
                    registry,
                    tid=tid,
                    prefix=prefix,
                    seen=seen,
                ):
                    continue
                document = row.get("ir")
                if not isinstance(document, dict):
                    registry.errors.append(f"{prefix}: ir must be an object")
                    continue
                try:
                    ir = PlaybookIR.from_dict(document)
                except IRValidationError as exc:
                    codes = ",".join(
                        sorted({issue.code for issue in exc.issues})
                    )
                    registry.errors.append(
                        f"{prefix}: IR contract failed ({codes})"
                    )
                    continue
                if ir.metadata.template_id != tid:
                    registry.errors.append(
                        f"{prefix}: metadata.template_id must equal {tid!r}"
                    )
                    continue
                if ir.id != tid:
                    registry.errors.append(
                        f"{prefix}: ir.id must equal {tid!r}"
                    )
                    continue
                if not _add_catalog_row(
                    registry,
                    tid=tid,
                    row=row,
                    template_kind="ir",
                    prefix=prefix,
                ):
                    continue
                registry.ir_templates[tid] = ir

    data = _parse_json(raw_config)
    if data is None:
        return registry
    if "__parse_error__" in data:
        registry.errors.append(
            "custom_templates_json is not valid JSON: "
            f"{data['__parse_error__']}"
        )
        return registry

    templates = data.get("templates")
    if templates is None:
        return registry
    if not isinstance(templates, list):
        registry.errors.append('"templates" must be a JSON array')
        return registry
    if len(templates) > MAX_TEMPLATES:
        registry.errors.append(
            f"custom_templates_json templates exceeds {MAX_TEMPLATES} entries"
        )
        templates = templates[:MAX_TEMPLATES]

    if templates and not allow_legacy_python:
        registry.warnings.append(
            "custom_templates_json contains legacy Python and was ignored; "
            "use custom_ir_templates_json or explicitly enable the lab-only "
            "allow_legacy_python_templates compatibility flag"
        )
        return registry

    for idx, row in enumerate(templates):
        prefix = f"templates[{idx}]"
        if not isinstance(row, dict):
            registry.errors.append(f"{prefix}: must be an object")
            continue

        tid = _normalized_id(row)
        if not _validate_id(
            registry,
            tid=tid,
            prefix=prefix,
            seen=seen,
        ):
            continue

        source = str(row.get("source") or "").strip()
        if not source:
            registry.errors.append(f"{prefix}: missing source")
            continue
        if len(source.encode("utf-8")) > MAX_LEGACY_SOURCE_BYTES:
            registry.errors.append(
                f"{prefix}: source exceeds {MAX_LEGACY_SOURCE_BYTES} "
                "UTF-8 bytes"
            )
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

        if not _add_catalog_row(
            registry,
            tid=tid,
            row=row,
            template_kind="legacy_python",
            prefix=prefix,
        ):
            continue
        registry.scaffolds[tid] = source

    return registry


def merged_catalog_by_id(org: OrgTemplateRegistry | None = None) -> dict[str, dict[str, Any]]:
    merged = shipped_catalog_by_id()
    if org:
        for row in org.catalog_rows:
            merged[row["id"]] = row
    return merged
