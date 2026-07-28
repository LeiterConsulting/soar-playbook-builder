"""Splunk Enterprise / dashboard → SOAR Playbook Builder deep-link (non-ES entry)."""

from __future__ import annotations

from typing import Any

from sidecar_url import append_query, build_sidecar_query_params


def build_sidecar_chat_url(base_handler_url: str, param: dict[str, Any]) -> str:
    base = base_handler_url.rstrip("/")
    if not base.endswith("/chat"):
        base = f"{base}/chat"
    return append_query(base, build_sidecar_query_params(param))


def resolve_splunk_link_params(
    *,
    sid: str | None = None,
    rule_name: str | None = None,
    src: str | None = None,
    dest: str | None = None,
    user: str | None = None,
    container_id: int | None = None,
    mode: str | None = "coach",
    tab: str | None = "respond",
) -> dict[str, Any]:
    """Map Splunk dashboard / alert tokens to sidecar query params."""
    out: dict[str, Any] = {}
    if container_id is not None:
        out["container_id"] = container_id
    if rule_name:
        out["rule_name"] = rule_name
    if mode:
        out["mode"] = mode
    if tab:
        out["tab"] = tab
    # Stash search context in rule_name when no rule token (dashboard drilldown).
    if not rule_name and sid:
        out["rule_name"] = f"Splunk search {sid[:48]}"
    hints: list[str] = []
    if src:
        hints.append(f"src={src}")
    if dest:
        hints.append(f"dest={dest}")
    if user:
        hints.append(f"user={user}")
    if sid:
        hints.append(f"sid={sid[:32]}")
    if hints and not out.get("investigation_id"):
        out["investigation_id"] = "|".join(hints)[:200]
    return out


def splunk_link_redirect_url(
    base_handler_url: str,
    *,
    sid: str | None = None,
    rule_name: str | None = None,
    src: str | None = None,
    dest: str | None = None,
    user: str | None = None,
    container_id: int | None = None,
    mode: str | None = "coach",
    tab: str | None = "respond",
) -> str:
    param = resolve_splunk_link_params(
        sid=sid,
        rule_name=rule_name,
        src=src,
        dest=dest,
        user=user,
        container_id=container_id,
        mode=mode,
        tab=tab,
    )
    return build_sidecar_chat_url(base_handler_url, param)


def splunk_link_status_message(param: dict[str, Any]) -> str:
    parts = ["Opening Playbook Builder from Splunk"]
    if param.get("container_id"):
        parts.append(f"case {param['container_id']}")
    if param.get("rule_name"):
        parts.append(f"context `{param['rule_name']}`")
    if param.get("mode") == "coach":
        parts.append("Response Coach")
    return " · ".join(parts)
