"""Run imported playbooks on a container with HITL gates and audit logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pattern_catalog import pattern_meta
from soar_rest import phantom_rest_call


def _truthy(val: Any) -> bool:
    return val in (True, 1, "1", "true", "True", "yes")


def _audit_log(event: str, detail: dict[str, Any]) -> None:
    try:
        import phantom.app as phantom

        payload = {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat(),
            **detail,
        }
        phantom.debug(f"PlaybookBuilder audit: {json.dumps(payload, default=str)[:2000]}")
    except Exception:  # noqa: BLE001
        pass


def _extract_run_id(resp: Any) -> int | None:
    if isinstance(resp, dict):
        for key in ("id", "playbook_run_id", "run_id"):
            raw = resp.get(key)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    continue
        data = resp.get("data")
        if isinstance(data, list) and data:
            return _extract_run_id(data[0])
    if isinstance(resp, list) and resp:
        return _extract_run_id(resp[0])
    return None


def run_playbook_on_container(
    request: Any,
    *,
    container_id: int,
    playbook_id: int,
    confirm: Any,
    destructive_confirm: Any = None,
    pattern_id: str | None = None,
) -> dict[str, Any]:
    """Start a playbook run on an existing container (uses caller SOAR session)."""
    if not _truthy(confirm):
        return {
            "status": "error",
            "error": "Run requires confirm=1 (use Run on this case after reviewing the draft).",
            "requires_confirm": True,
        }

    org = getattr(request, "_pb_org_registry", None)
    meta = pattern_meta(pattern_id, org_registry=org) if pattern_id else {}
    tier = meta.get("tier", "safe")
    if tier == "destructive" and not _truthy(destructive_confirm):
        return {
            "status": "error",
            "error": (
                "Destructive template — run requires destructive_confirm=1. "
                f"Template tier: {tier}. Actions may disable users, block IPs, or quarantine endpoints."
            ),
            "tier": tier,
            "requires_destructive_confirm": True,
            "destructive_actions": meta.get("destructive_actions") or [],
        }

    body = {"container_id": container_id, "playbook_id": playbook_id, "run": True}
    ok, resp = phantom_rest_call("POST", "playbook_run", body=body, request=request)
    if not ok:
        _audit_log(
            "playbook_run_failed",
            {
                "container_id": container_id,
                "playbook_id": playbook_id,
                "pattern_id": pattern_id,
                "tier": tier,
                "error": str(resp)[:500],
            },
        )
        return {"status": "error", "error": str(resp), "tier": tier}

    run_id = _extract_run_id(resp)
    _audit_log(
        "playbook_run_started",
        {
            "container_id": container_id,
            "playbook_id": playbook_id,
            "playbook_run_id": run_id,
            "pattern_id": pattern_id,
            "tier": tier,
            "transport": "soar_rest",
        },
    )
    return {
        "status": "success",
        "container_id": container_id,
        "playbook_id": playbook_id,
        "playbook_run_id": run_id,
        "tier": tier,
        "message": f"Started playbook run {run_id or '(pending)'} on container {container_id}",
        "raw": resp if isinstance(resp, dict) else {"result": resp},
    }
