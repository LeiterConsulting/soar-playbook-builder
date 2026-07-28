"""Deterministic Playbook IR preflight and structured GapReport."""

from .preflight import preflight
from .report import GapReport, gap_report_json_schema

__all__ = ["GapReport", "gap_report_json_schema", "preflight"]
