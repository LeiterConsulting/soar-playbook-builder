"""Orchestrate ordered deterministic validation rules."""

from __future__ import annotations

from datetime import datetime

from capability.schema import CapabilityIndex
from ir.schema import PlaybookIR

from .report import GapReport
from .rules import RULES
from .rules.base import ValidationContext


def _evaluated_at(value: datetime | str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("evaluated_at must be an ISO-8601 timestamp") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("evaluated_at must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None:
        raise ValueError("evaluated_at must include a timezone")
    return parsed


def preflight(
    ir: PlaybookIR,
    index: CapabilityIndex,
    *,
    evaluated_at: datetime | str,
    stale_after_seconds: int = 86_400,
) -> GapReport:
    """Return a stable GapReport; this function never consults a model."""
    if stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be positive")
    evaluated = _evaluated_at(evaluated_at)
    context = ValidationContext(
        ir=ir,
        index=index,
        evaluated_at=evaluated,
        stale_after_seconds=stale_after_seconds,
    )
    for rule in RULES:
        rule.run(context)
    return GapReport.build(
        gaps=context.gaps,
        substitutions=context.substitutions,
        index_version=index.index_version or index.version,
        index_age_seconds=context.index_age_seconds,
        evaluated_at=evaluated.isoformat(),
        ir_sha256=ir.sha256(),
    )
