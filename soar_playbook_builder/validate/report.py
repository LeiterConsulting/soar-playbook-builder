"""Strict, deterministic GapReport value objects and JSON Schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

GapSeverity = Literal["blocker", "warning", "info"]
ReportStatus = Literal["ok", "degraded", "blocked"]

_SEVERITY_ORDER = {"blocker": 0, "warning": 1, "info": 2}
PREFLIGHT_GAP_IDS = frozenset(
    {
        "ACTION_APP_UNKNOWN",
        "ACTION_INSTALLATION_UNVERIFIED",
        "ACTION_NOT_FOUND",
        "ALL_JOIN_UNREACHABLE",
        "APP_INSTALLATION_UNVERIFIED",
        "ASSET_APP_MISMATCH",
        "ASSET_MISSING",
        "ASSET_NOT_CONFIGURED",
        "ASSET_UNBOUND",
        "ASSET_UNHEALTHY",
        "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
        "CAPABILITY_INDEX_VERSION_MISMATCH",
        "CONTAINS_MISMATCH",
        "CONTAINS_UNVERIFIED",
        "DATAPATH_UNKNOWN",
        "DATAPATH_UNVERIFIED",
        "DESTRUCTIVE_ACTION_REVIEW_REQUIRED",
        "EGRESS_REQUIRED",
        "EGRESS_UNKNOWN",
        "INDEX_HARVEST_DEGRADED",
        "INDEX_STALE",
        "INDEX_TIMESTAMP_MISSING",
        "OBJECT_INVENTORY_UNAVAILABLE",
        "OUTPUT_DATAPATH_UNKNOWN",
        "PARAMETER_REQUIRED",
        "PARAMETER_TYPE_MISMATCH",
        "PARAMETER_UNKNOWN",
        "PERMISSION_DENIED",
        "PERMISSION_UNVERIFIED",
        "PLAYBOOK_INPUT_UNDECLARED",
        "REFERENCED_OBJECT_MISSING",
    }
)
GENERATION_GAP_IDS = frozenset(
    {
        "MODEL_OUTPUT_INVALID",
        "MODEL_PROVIDER_FAILED",
        "MODEL_REPAIR_EXHAUSTED",
    }
)
SUPPORTED_GAP_IDS = PREFLIGHT_GAP_IDS | GENERATION_GAP_IDS


@dataclass(frozen=True)
class ArtifactNeeded:
    type: str
    name: str
    version: str = ""
    splunkbase_id: str = ""
    transfer_note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "name": self.name,
            "version": self.version,
            "splunkbase_id": self.splunkbase_id,
            "transfer_note": self.transfer_note,
        }


@dataclass(frozen=True)
class Remediation:
    offline_capable: bool
    steps: tuple[str, ...]
    artifacts_needed: tuple[ArtifactNeeded, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "offline_capable": self.offline_capable,
            "steps": list(self.steps),
            "artifacts_needed": [
                artifact.to_dict() for artifact in self.artifacts_needed
            ],
        }


@dataclass(frozen=True)
class Gap:
    id: str
    severity: GapSeverity
    node: str
    summary: str
    detail: dict[str, Any]
    remediation: Remediation

    def __post_init__(self) -> None:
        if self.id not in SUPPORTED_GAP_IDS:
            raise ValueError(f"unsupported gap id: {self.id!r}")
        if self.severity not in _SEVERITY_ORDER:
            raise ValueError(f"invalid gap severity: {self.severity!r}")
        try:
            json.dumps(self.detail, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("gap detail must be finite JSON") from exc

    def sort_key(self) -> tuple[Any, ...]:
        return (
            _SEVERITY_ORDER[self.severity],
            self.node,
            self.id,
            json.dumps(self.detail, sort_keys=True, separators=(",", ":")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "node": self.node,
            "summary": self.summary,
            "detail": self.detail,
            "remediation": self.remediation.to_dict(),
        }


@dataclass(frozen=True)
class Substitution:
    node: str
    source_app: str
    source_action: str
    replacement_app: str
    replacement_action: str
    reason: str
    automatic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "from": {
                "app": self.source_app,
                "action": self.source_action,
            },
            "to": {
                "app": self.replacement_app,
                "action": self.replacement_action,
            },
            "reason": self.reason,
            "automatic": self.automatic,
        }


@dataclass(frozen=True)
class GapReport:
    status: ReportStatus
    gaps: tuple[Gap, ...]
    substitutions: tuple[Substitution, ...]
    index_version: str
    index_age_seconds: int | None
    evaluated_at: str
    ir_sha256: str

    @classmethod
    def build(
        cls,
        *,
        gaps: list[Gap],
        substitutions: list[Substitution],
        index_version: str,
        index_age_seconds: int | None,
        evaluated_at: str,
        ir_sha256: str,
    ) -> GapReport:
        ordered_gaps = tuple(sorted(gaps, key=Gap.sort_key))
        ordered_substitutions = tuple(
            sorted(
                substitutions,
                key=lambda row: (
                    row.node,
                    row.source_app,
                    row.source_action,
                    row.replacement_app,
                    row.replacement_action,
                ),
            )
        )
        if any(gap.severity == "blocker" for gap in ordered_gaps):
            status: ReportStatus = "blocked"
        elif any(gap.severity == "warning" for gap in ordered_gaps):
            status = "degraded"
        else:
            status = "ok"
        return cls(
            status=status,
            gaps=ordered_gaps,
            substitutions=ordered_substitutions,
            index_version=index_version,
            index_age_seconds=index_age_seconds,
            evaluated_at=evaluated_at,
            ir_sha256=ir_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "substitutions": [
                substitution.to_dict()
                for substitution in self.substitutions
            ],
            "index_version": self.index_version,
            "index_age_seconds": self.index_age_seconds,
            "evaluated_at": self.evaluated_at,
            "ir_sha256": self.ir_sha256,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _closed(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def gap_report_json_schema() -> dict[str, Any]:
    """Return the Draft 2020-12 contract used by tests and external callers."""
    string = {"type": "string"}
    artifact = _closed(
        {
            "type": string,
            "name": string,
            "version": string,
            "splunkbase_id": string,
            "transfer_note": string,
        },
        ["type", "name", "version", "splunkbase_id", "transfer_note"],
    )
    remediation = _closed(
        {
            "offline_capable": {"type": "boolean"},
            "steps": {"type": "array", "items": string, "minItems": 1},
            "artifacts_needed": {"type": "array", "items": artifact},
        },
        ["offline_capable", "steps", "artifacts_needed"],
    )
    gap = _closed(
        {
            "id": {"enum": sorted(SUPPORTED_GAP_IDS)},
            "severity": {"enum": ["blocker", "warning", "info"]},
            "node": string,
            "summary": string,
            "detail": {"type": "object"},
            "remediation": remediation,
        },
        ["id", "severity", "node", "summary", "detail", "remediation"],
    )
    substitution = _closed(
        {
            "node": string,
            "from": _closed({"app": string, "action": string}, ["app", "action"]),
            "to": _closed({"app": string, "action": string}, ["app", "action"]),
            "reason": string,
            "automatic": {"type": "boolean"},
        },
        ["node", "from", "to", "reason", "automatic"],
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:soar-playbook-builder:gap-report:1.0.0",
        **_closed(
            {
                "status": {"enum": ["ok", "degraded", "blocked"]},
                "gaps": {"type": "array", "items": gap},
                "substitutions": {
                    "type": "array",
                    "items": substitution,
                },
                "index_version": string,
                "index_age_seconds": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                },
                "evaluated_at": string,
                "ir_sha256": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
            },
            [
                "status",
                "gaps",
                "substitutions",
                "index_version",
                "index_age_seconds",
                "evaluated_at",
                "ir_sha256",
            ],
        ),
    }
