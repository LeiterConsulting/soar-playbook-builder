"""Shared rule context; all output is deterministic and model-free."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from capability.schema import ActionCapability, AppCapability, CapabilityIndex
from ir.schema import PlaybookIR
from validate.remediation import remediation_for
from validate.report import Gap, GapSeverity, Substitution


class Rule(Protocol):
    def run(self, context: ValidationContext) -> None: ...


def normalize(value: str) -> str:
    return " ".join(value.strip().casefold().replace("-", " ").replace("_", " ").split())


def action_permission_key(app: str, action: str) -> str:
    return f"{normalize(app)}:{normalize(action)}"


@dataclass
class ValidationContext:
    ir: PlaybookIR
    index: CapabilityIndex
    evaluated_at: datetime
    stale_after_seconds: int
    gaps: list[Gap] = field(default_factory=list)
    substitutions: list[Substitution] = field(default_factory=list)
    resolved_apps: dict[str, AppCapability] = field(default_factory=dict)
    resolved_actions: dict[str, ActionCapability] = field(default_factory=dict)
    index_age_seconds: int | None = None
    _seen: set[str] = field(default_factory=set)

    def add_gap(
        self,
        *,
        gap_id: str,
        severity: GapSeverity,
        node: str,
        summary: str,
        detail: dict[str, Any],
    ) -> None:
        normalized_detail = dict(detail)
        if node and "node" not in normalized_detail:
            normalized_detail["node"] = node
        dedupe_key = "|".join(
            (
                gap_id,
                node,
                json.dumps(
                    normalized_detail,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            )
        )
        if dedupe_key in self._seen:
            return
        self._seen.add(dedupe_key)
        self.gaps.append(
            Gap(
                id=gap_id,
                severity=severity,
                node=node,
                summary=summary,
                detail=normalized_detail,
                remediation=remediation_for(
                    gap_id,
                    normalized_detail,
                    self.index,
                ),
            )
        )

    def resolve_app(self, requested: str) -> AppCapability | None:
        expected = normalize(requested)
        for key in sorted(self.index.apps):
            app = self.index.apps[key]
            if expected in {
                normalize(key),
                normalize(app.name),
                normalize(app.product_name),
            }:
                return app
        return None

    @staticmethod
    def resolve_action(
        app: AppCapability,
        requested: str,
    ) -> ActionCapability | None:
        expected = normalize(requested)
        return next(
            (
                action
                for action in sorted(app.actions, key=lambda item: normalize(item.name))
                if normalize(action.name) == expected
            ),
            None,
        )
