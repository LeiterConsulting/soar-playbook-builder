"""Deterministic human-readable rendering of a GapReport."""

from __future__ import annotations

from .report import GapReport


def render_gap_report(report: GapReport) -> str:
    """Render only entities already present in the report."""
    lines = [
        f"Preflight status: {report.status}",
        f"IR: {report.ir_sha256}",
        f"Capability index: {report.index_version}",
        (
            f"Index age: {report.index_age_seconds} seconds"
            if report.index_age_seconds is not None
            else "Index age: unknown"
        ),
    ]
    if not report.gaps:
        lines.append("No gaps detected.")
    for gap in report.gaps:
        location = f" [{gap.node}]" if gap.node else ""
        lines.append(f"- {gap.severity.upper()} {gap.id}{location}: {gap.summary}")
        for index, step in enumerate(gap.remediation.steps, start=1):
            lines.append(f"  {index}. {step}")
    for substitution in report.substitutions:
        lines.append(
            "- SUBSTITUTION [{}]: {}:{} -> {}:{} ({})".format(
                substitution.node,
                substitution.source_app,
                substitution.source_action,
                substitution.replacement_app,
                substitution.replacement_action,
                substitution.reason,
            )
        )
    return "\n".join(lines) + "\n"
