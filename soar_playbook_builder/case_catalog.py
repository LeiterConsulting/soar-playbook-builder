"""List SOAR cases (containers) and org sample cases for the sidecar case picker."""

from __future__ import annotations

import json
from typing import Any

from soar_rest import phantom_rest_call

DEFAULT_SAMPLE_CASES: list[dict[str, Any]] = [
    {
        "id": 9001,
        "name": "Failed Logins — jdoe (sample)",
        "severity": "high",
        "status": "open",
        "label": "es_notable_response",
        "source": "sample",
        "event_id": "sample-event-failed-logins-001",
        "rule_name": "Access - Excessive Failed Logins",
        "fixture_pattern_id": "failed-logins-okta",
        "demo_tier": "destructive",
        "summary": "user jdoe · src 10.0.0.5 · ES notable export · Okta disable (lab only)",
    },
    {
        "id": 9002,
        "name": "Phishing URL — finance user (sample)",
        "severity": "medium",
        "status": "open",
        "label": "es_notable_response",
        "source": "sample",
        "event_id": "sample-event-phish-002",
        "rule_name": "Malicious URL Click",
        "fixture_pattern_id": "phishing-enrichment",
        "demo_tier": "safe",
        "showcase_recommended": True,
        "summary": "suspicious link in email · user finance_bot · safe for demos",
    },
    {
        "id": 9003,
        "name": "Insider threat — critical (sample)",
        "severity": "critical",
        "status": "open",
        "label": "ueba_insider",
        "source": "sample",
        "event_id": "sample-event-insider-003",
        "rule_name": "Insider Threat - UEBA",
        "fixture_pattern_id": "insider-threat-ad",
        "demo_tier": "destructive",
        "summary": "UEBA score elevated · user contractor_a · AD actions (lab only)",
    },
    {
        "id": 9004,
        "name": "ES Notable — suspicious source IP (sample)",
        "severity": "medium",
        "status": "open",
        "label": "es_notable_response",
        "source": "sample",
        "event_id": "sample-event-es-notable-004",
        "rule_name": "Suspicious Network Activity",
        "fixture_pattern_id": "es-notable-response",
        "demo_tier": "safe",
        "showcase_recommended": True,
        "summary": "ES notable export · src 203.0.113.10 · note-only playbook",
    },
    {
        "id": 9005,
        "name": "Hello World — minimal demo (sample)",
        "severity": "low",
        "status": "open",
        "label": "pb_demo",
        "source": "sample",
        "event_id": "sample-event-hello-005",
        "rule_name": "Playbook Builder Demo",
        "fixture_pattern_id": "hello",
        "demo_tier": "safe",
        "showcase_recommended": True,
        "summary": "smallest fixture · verify Run tab end-to-end with hello template",
    },
]


def sample_ids() -> list[int]:
    """Built-in demo sample case ids for environment checks and docs."""
    out: list[int] = []
    for row in DEFAULT_SAMPLE_CASES:
        try:
            out.append(int(row["id"]))
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _rows_from_rest(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def parse_sample_cases_json(raw: str | None) -> list[dict[str, Any]]:
    """Parse asset sample_cases_json; ids must be numeric."""
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = data if isinstance(data, list) else data.get("cases") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        normalized = dict(row)
        normalized["source"] = normalized.get("source") or "sample"
        out.append(normalized)
    return out


def _normalize_container(row: dict[str, Any]) -> dict[str, Any]:
    cid = row.get("id")
    return {
        "id": cid,
        "name": row.get("name") or f"Case {cid}",
        "severity": row.get("severity") or "",
        "status": row.get("status") or "",
        "label": row.get("label") or row.get("tags") or "",
        "source": "soar",
        "event_id": "",
        "rule_name": "",
        "summary": _container_summary(row),
    }


def _container_summary(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if row.get("severity"):
        parts.append(str(row["severity"]))
    if row.get("label"):
        parts.append(f"label {row['label']}")
    if row.get("status"):
        parts.append(str(row["status"]))
    return " · ".join(parts) if parts else "SOAR case"


def _artifact_hints(container_id: int, request: Any | None) -> dict[str, str]:
    """Best-effort event_id / rule_name from first artifacts."""
    ok, resp = phantom_rest_call(
        "GET",
        "artifact",
        params={"_page_size": 5, "_filter": f'container_id="{container_id}"'},
        request=request,
    )
    if not ok:
        return {}
    hints: dict[str, str] = {}
    for art in _rows_from_rest(resp):
        cef = art.get("cef") if isinstance(art.get("cef"), dict) else {}
        for key, target in (
            ("event_id", "event_id"),
            ("eventId", "event_id"),
            ("rule_name", "rule_name"),
            ("name", "rule_name"),
        ):
            if target not in hints:
                val = cef.get(key) or art.get(key)
                if val:
                    hints[target] = str(val)
        if hints.get("event_id") and hints.get("rule_name"):
            break
    return hints


def lookup_sample_case(
    container_id: int | str,
    sample_cases_json: str | None = None,
) -> dict[str, Any] | None:
    """Return a configured sample case row when container_id matches."""
    try:
        target = int(container_id)
    except (TypeError, ValueError):
        return None
    samples = parse_sample_cases_json(sample_cases_json) or list(DEFAULT_SAMPLE_CASES)
    for row in samples:
        try:
            if int(row.get("id")) == target:
                return dict(row)
        except (TypeError, ValueError):
            continue
    return None


def list_cases_payload(
    request: Any,
    *,
    sample_cases_json: str | None = None,
    page_size: int = 20,
    enrich_artifacts: bool = True,
) -> dict[str, Any]:
    """Return recent SOAR containers plus configured sample cases."""
    samples = parse_sample_cases_json(sample_cases_json) or list(DEFAULT_SAMPLE_CASES)
    live: list[dict[str, Any]] = []
    error: str | None = None

    ok, resp = phantom_rest_call(
        "GET",
        "container",
        params={"_page_size": page_size, "_sort": "id", "_order": "desc"},
        request=request,
    )
    if ok:
        for row in _rows_from_rest(resp):
            if row.get("id") is None:
                continue
            case = _normalize_container(row)
            if enrich_artifacts:
                try:
                    cid = int(case["id"])
                    hints = _artifact_hints(cid, request)
                    case["event_id"] = hints.get("event_id", "")
                    case["rule_name"] = hints.get("rule_name", "")
                except (TypeError, ValueError):
                    pass
            live.append(case)
    else:
        error = str(resp)

    # Samples first for demos; then live cases not duplicating sample ids.
    sample_ids = {str(c.get("id")) for c in samples}
    merged = list(samples)
    for case in live:
        if str(case.get("id")) not in sample_ids:
            merged.append(case)

    return {
        "status": "success",
        "cases": merged,
        "sample_count": len(samples),
        "live_count": len(live),
        "showcase_sample_ids": [
            int(c["id"])
            for c in samples
            if c.get("showcase_recommended") and c.get("id") is not None
        ],
        "message": (
            f"{len(merged)} cases available ({len(samples)} sample, {len(live)} from SOAR)."
            if merged
            else "No cases found — use sample cases below or export a notable to SOAR."
        ),
        "error_detail": error if not live and error else None,
    }
