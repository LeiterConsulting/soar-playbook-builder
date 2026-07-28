"""Sidecar URL query building (no SOAR/phantom dependencies)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


def build_sidecar_query_params(param: dict[str, Any]) -> list[tuple[str, str]]:
    """Build sidecar URL query pairs from connector/playbook parameters."""
    pairs: list[tuple[str, str]] = []
    for key in ("playbook_id", "container_id", "event_id", "investigation_id"):
        raw = param.get(key)
        if raw is None or raw == "":
            continue
        try:
            if key.endswith("_id") and key != "investigation_id":
                pairs.append((key, str(int(raw))))
            else:
                pairs.append((key, str(raw)))
        except (TypeError, ValueError):
            pairs.append((key, str(raw)))
    rule = param.get("rule_name")
    if rule:
        pairs.append(("rule_name", str(rule)))
    mode = param.get("mode")
    if mode:
        pairs.append(("mode", str(mode)))
    tab = param.get("tab")
    if tab:
        pairs.append(("tab", str(tab)))
    return pairs


def append_query(url: str, params: list[tuple[str, str]]) -> str:
    if not params:
        return url
    qs = "&".join(f"{k}={quote(v, safe='')}" for k, v in params)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{qs}"
