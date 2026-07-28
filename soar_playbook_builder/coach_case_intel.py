"""Read-only case intelligence for Coach L1 (playbook runs, labels)."""

from __future__ import annotations

from typing import Any

from soar_rest import phantom_rest_call


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


def fetch_container_playbook_runs(container_id: int, request: Any | None = None) -> list[dict[str, Any]]:
    """Recent playbook runs on a container (best-effort SOAR REST)."""
    filt = f'container_id="{container_id}"'
    ok, resp = phantom_rest_call(
        "GET",
        "playbook_run",
        params={"_page_size": 10, "_sort": "id", "_order": "desc", "_filter": filt},
        request=request,
    )
    if not ok:
        return []
    out: list[dict[str, Any]] = []
    for row in _rows_from_rest(resp):
        out.append(
            {
                "id": row.get("id"),
                "playbook_id": row.get("playbook_id") or row.get("playbook"),
                "status": row.get("status") or row.get("status_message"),
                "name": row.get("playbook_name") or row.get("name"),
            }
        )
    return out


def coach_case_intel(container_id: int | None, request: Any | None = None) -> dict[str, Any]:
    """Structured L1 intel merged into coach_suggest."""
    if container_id is None:
        return {"recent_runs": [], "run_count": 0}
    runs = fetch_container_playbook_runs(int(container_id), request=request)
    return {
        "recent_runs": runs[:5],
        "run_count": len(runs),
    }
