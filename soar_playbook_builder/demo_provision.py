"""Provision real SOAR demo containers from runtime fixtures for playbook vetting."""

from __future__ import annotations

import time
from typing import Any

from case_catalog import lookup_sample_case
from runtime_fixtures import RUNTIME_FIXTURES, RuntimeFixture, fixture_for
from soar_rest import phantom_rest_call

DEMO_LABEL = "pb_demo"


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


def _extract_id(resp: Any) -> int | None:
    if isinstance(resp, dict) and resp.get("id") is not None:
        return int(resp["id"])
    for row in _rows_from_rest(resp):
        if row.get("id") is not None:
            return int(row["id"])
    return None


def resolve_fixture_pattern(
    *,
    pattern_id: str | None = None,
    sample_id: int | str | None = None,
    sample_cases_json: str | None = None,
) -> str | None:
    if pattern_id and pattern_id in RUNTIME_FIXTURES:
        return pattern_id
    if sample_id is not None:
        row = lookup_sample_case(sample_id, sample_cases_json)
        if row:
            pid = row.get("fixture_pattern_id")
            if pid and pid in RUNTIME_FIXTURES:
                return str(pid)
    return None


def _merge_sample_cef(
    fixture: RuntimeFixture,
    sample_row: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Copy fixture artifacts and inject ES/SOAR correlation fields from sample metadata."""
    if not sample_row:
        return list(fixture.artifacts)
    event_id = str(sample_row.get("event_id") or "").strip()
    rule_name = str(sample_row.get("rule_name") or "").strip()
    merged: list[dict[str, Any]] = []
    for art in fixture.artifacts:
        row = {
            "name": art.get("name") or "artifact",
            "label": art.get("label") or "event",
            "cef": dict(art.get("cef") or {}),
        }
        if event_id:
            row["cef"].setdefault("event_id", event_id)
            row["cef"].setdefault("eventId", event_id)
        if rule_name:
            row["cef"].setdefault("rule_name", rule_name)
            row["cef"].setdefault("name", rule_name)
        merged.append(row)
    if not merged and (event_id or rule_name):
        cef: dict[str, Any] = {}
        if event_id:
            cef["event_id"] = event_id
            cef["eventId"] = event_id
        if rule_name:
            cef["rule_name"] = rule_name
            cef["name"] = rule_name
        merged.append({"name": "es_notable", "label": "event", "cef": cef})
    return merged


def provision_demo_case(
    request: Any,
    *,
    pattern_id: str | None = None,
    sample_id: int | str | None = None,
    sample_cases_json: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Create a SOAR container + artifacts from a runtime fixture."""
    sample_row = lookup_sample_case(sample_id, sample_cases_json) if sample_id is not None else None
    pid = resolve_fixture_pattern(
        pattern_id=pattern_id,
        sample_id=sample_id,
        sample_cases_json=sample_cases_json,
    )
    if not pid:
        return {
            "status": "error",
            "error": "Unknown demo pattern — pick a sample case or pass pattern_id / sample_id.",
        }
    fixture = fixture_for(pid)
    if not fixture:
        return {"status": "error", "error": f"No fixture for pattern {pid}"}

    if not confirm:
        tier = sample_row.get("demo_tier") if sample_row else fixture.tier
        tier_note = f" ({tier} tier)" if tier else ""
        return {
            "status": "success",
            "needs_confirm": True,
            "pattern_id": pid,
            "sample_id": sample_id,
            "message": f"Create demo case for **{pid}** on SOAR{tier_note}?",
            "hint": "Pass confirm=1 to provision container + artifacts.",
        }

    tag = str(int(time.time()))[-6:]
    display = (sample_row or {}).get("name") or f"PB Demo — {pid}"
    body = {
        "name": f"{display.replace(' (sample)', '')} [{tag}]",
        "description": f"Playbook Builder demo — pattern {pid}",
        "label": (sample_row or {}).get("label") or DEMO_LABEL,
        "severity": (sample_row or {}).get("severity") or fixture.container_severity,
        "status": "new",
    }
    ok, resp = phantom_rest_call("POST", "container", body=body, request=request)
    if not ok:
        return {"status": "error", "error": f"Could not create container: {resp}"}

    container_id = _extract_id(resp)
    if container_id is None:
        return {"status": "error", "error": "Container created but id missing in response"}

    artifacts = _merge_sample_cef(fixture, sample_row)
    art_err = _create_artifacts(request, container_id, artifacts)
    if art_err:
        return {
            "status": "partial",
            "container_id": container_id,
            "pattern_id": pid,
            "error": art_err,
            "message": f"Demo case {container_id} created; artifact error: {art_err}",
        }

    return {
        "status": "success",
        "container_id": container_id,
        "pattern_id": pid,
        "artifact_count": len(artifacts),
        "event_id": (sample_row or {}).get("event_id"),
        "rule_name": (sample_row or {}).get("rule_name"),
        "message": f"Demo case **{container_id}** ready for **{pid}**.",
    }


def _create_artifacts(request: Any, container_id: int, artifacts: list[dict[str, Any]]) -> str | None:
    for art in artifacts:
        cef = art.get("cef") or {}
        cef_types = {k: [""] for k in cef.keys()}
        body = {
            "container_id": container_id,
            "name": art.get("name") or "artifact",
            "label": art.get("label") or "event",
            "severity": "Medium",
            "cef": cef,
            "cef_types": cef_types,
        }
        ok, resp = phantom_rest_call("POST", "artifact", body=body, request=request)
        if not ok:
            return str(resp)
    return None
