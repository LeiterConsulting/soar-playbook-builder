"""ES → SOAR Playbook Builder deep-link: resolve case context and redirect to sidecar."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from sidecar_url import append_query, build_sidecar_query_params
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


def _artifact_matches_event(artifact: dict[str, Any], event_id: str) -> bool:
    needle = event_id.strip().lower()
    if not needle:
        return False
    for key in ("event_id", "eventId", "externalId", "external_id", "notable_event_id"):
        val = artifact.get(key)
        if val is not None and str(val).strip().lower() == needle:
            return True
    cef = artifact.get("cef") if isinstance(artifact.get("cef"), dict) else {}
    for key in ("event_id", "eventId", "externalId", "external_id", "notable_event_id"):
        val = cef.get(key)
        if val is not None and str(val).strip().lower() == needle:
            return True
    cef_val = str(artifact.get("cef_value") or "")
    return needle in cef_val.lower()


def find_container_id_for_event(event_id: str, request: Any | None = None) -> int | None:
    """Best-effort lookup of SOAR case ID from ES notable event_id in artifacts."""
    event_id = (event_id or "").strip()
    if not event_id:
        return None

    # Try REST filters on common CEF field names first (fast path).
    for field in ("event_id", "eventId", "externalId", "external_id"):
        filt = f'cef.{field}="{event_id}"'
        ok, resp = phantom_rest_call(
            "GET",
            "artifact",
            params={"_page_size": 5, "_filter": filt},
            request=request,
        )
        if not ok:
            continue
        for row in _rows_from_rest(resp):
            cid = row.get("container_id") or row.get("container")
            if cid is not None:
                try:
                    return int(cid)
                except (TypeError, ValueError):
                    continue

    # Fallback: scan recent containers' artifacts (export timing / field naming varies).
    ok, resp = phantom_rest_call(
        "GET",
        "container",
        params={"_page_size": 30, "_sort": "id", "_order": "desc"},
        request=request,
    )
    if not ok:
        return None
    for container in _rows_from_rest(resp):
        cid = container.get("id")
        if cid is None:
            continue
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            continue
        arts_ok, arts_resp = phantom_rest_call(
            "GET",
            "artifact",
            params={"_page_size": 50, "_filter": f'container_id="{cid_int}"'},
            request=request,
        )
        if not arts_ok:
            continue
        for art in _rows_from_rest(arts_resp):
            if _artifact_matches_event(art, event_id):
                return cid_int
    return None


def build_sidecar_chat_url(base_handler_url: str, param: dict[str, Any]) -> str:
    """Build full sidecar /chat URL with investigation context query params."""
    base = base_handler_url.rstrip("/")
    if not base.endswith("/chat"):
        base = f"{base}/chat"
    return append_query(base, build_sidecar_query_params(param))


def resolve_es_link_params(
    *,
    event_id: str | None = None,
    rule_name: str | None = None,
    investigation_id: str | None = None,
    container_id: int | None = None,
    playbook_id: int | None = None,
    request: Any | None = None,
) -> dict[str, Any]:
    """Merge explicit params with container lookup from ES event_id."""
    out: dict[str, Any] = {}
    if playbook_id is not None:
        out["playbook_id"] = playbook_id
    if rule_name:
        out["rule_name"] = rule_name
    if investigation_id:
        out["investigation_id"] = investigation_id
    if event_id:
        out["event_id"] = event_id

    cid = container_id
    if cid is None and event_id:
        cid = find_container_id_for_event(event_id, request=request)
    if cid is not None:
        out["container_id"] = cid
    return out


def es_link_redirect_url(
    base_handler_url: str,
    *,
    event_id: str | None = None,
    rule_name: str | None = None,
    investigation_id: str | None = None,
    container_id: int | None = None,
    playbook_id: int | None = None,
    request: Any | None = None,
) -> str:
    param = resolve_es_link_params(
        event_id=event_id,
        rule_name=rule_name,
        investigation_id=investigation_id,
        container_id=container_id,
        playbook_id=playbook_id,
        request=request,
    )
    return build_sidecar_chat_url(base_handler_url, param)


def es_link_status_message(param: dict[str, Any]) -> str:
    """Human-readable hint for redirect landing (optional query ?link_status=1)."""
    parts = ["Opening Playbook Builder"]
    if param.get("container_id"):
        parts.append(f"linked to case {param['container_id']}")
    elif param.get("event_id"):
        parts.append(
            f"for ES event {param['event_id']} (no SOAR case found yet — export notable to SOAR to enable Run on this case)"
        )
    if param.get("rule_name"):
        parts.append(f"rule `{param['rule_name']}`")
    return " · ".join(parts)


def quote_rule_name(rule_name: str) -> str:
    return quote(rule_name or "", safe="")
