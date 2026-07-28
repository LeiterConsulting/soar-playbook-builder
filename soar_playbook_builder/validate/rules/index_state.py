"""Capability-index version, harvest, and staleness rules."""

from __future__ import annotations

from datetime import datetime

from .base import ValidationContext


class IndexStateRule:
    def run(self, context: ValidationContext) -> None:
        actual_version = context.index.index_version or context.index.version
        expected_version = context.ir.metadata.capability_index_version
        if expected_version and actual_version and expected_version != actual_version:
            context.add_gap(
                gap_id="CAPABILITY_INDEX_VERSION_MISMATCH",
                severity="blocker",
                node="",
                summary="IR capability version does not match the loaded index",
                detail={
                    "expected": expected_version,
                    "actual": actual_version,
                },
            )

        if context.index.harvest_status != "ok":
            context.add_gap(
                gap_id="INDEX_HARVEST_DEGRADED",
                severity="warning",
                node="",
                summary="Capability harvest is not fully verified",
                detail={
                    "status": context.index.harvest_status,
                    "errors": sorted(context.index.harvest_errors),
                },
            )

        if not context.index.built_at:
            context.add_gap(
                gap_id="INDEX_TIMESTAMP_MISSING",
                severity="warning",
                node="",
                summary="Capability index age cannot be established",
                detail={"built_at": ""},
            )
            return
        try:
            built_at = datetime.fromisoformat(
                context.index.built_at.replace("Z", "+00:00")
            )
            if built_at.tzinfo is None:
                raise ValueError("timestamp lacks timezone")
        except ValueError:
            context.add_gap(
                gap_id="INDEX_TIMESTAMP_MISSING",
                severity="warning",
                node="",
                summary="Capability index timestamp is invalid",
                detail={"built_at": context.index.built_at},
            )
            return
        age = int((context.evaluated_at - built_at).total_seconds())
        if age < 0:
            context.add_gap(
                gap_id="INDEX_TIMESTAMP_MISSING",
                severity="warning",
                node="",
                summary="Capability index timestamp is in the future",
                detail={"built_at": context.index.built_at, "age_seconds": age},
            )
            return
        context.index_age_seconds = age
        if age > context.stale_after_seconds:
            context.add_gap(
                gap_id="INDEX_STALE",
                severity="warning",
                node="",
                summary="Capability index is older than the configured threshold",
                detail={
                    "age_seconds": age,
                    "threshold_seconds": context.stale_after_seconds,
                    "built_at": context.index.built_at,
                },
            )
