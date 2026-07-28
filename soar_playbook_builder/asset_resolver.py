"""Resolve scaffold asset keys to configured SOAR asset names before import."""

from __future__ import annotations

import json
import re
from typing import Any

from preview_visual import ASSET_LANES, extract_phantom_acts
from soar_rest import django_request_rest, phantom_rest_call

# Scaffold keys (phantom.act assets=[...]) → SOAR product / name heuristics
ASSET_TYPE_HINTS: dict[str, dict[str, list[str]]] = {
    "servicenow": {
        "product_codes": ["servicenow"],
        "product_names": ["servicenow", "service now"],
        "name_tokens": ["servicenow", "snow", "service_now"],
    },
    "soar": {
        "product_codes": ["phantom", "soar", "splunk_soar"],
        "product_names": ["splunk soar", "phantom", "soar"],
        "name_tokens": ["soar", "phantom", "local", "default"],
    },
    "splunk_enterprise": {
        "product_codes": ["splunk", "splunk_enterprise", "splunkenterprise"],
        "product_names": ["splunk", "splunk enterprise"],
        "name_tokens": ["splunk", "hec", "enterprise"],
    },
    "clearpass_cppm": {
        "product_codes": ["clearpass", "clearpass_cppm", "aruba_clearpass"],
        "product_names": ["clearpass", "aruba clearpass"],
        "name_tokens": ["clearpass", "cppm", "aruba"],
    },
    "okta": {
        "product_codes": ["okta"],
        "product_names": ["okta"],
        "name_tokens": ["okta"],
    },
    "panw": {
        "product_codes": ["panw", "panorama", "wildfire"],
        "product_names": ["palo alto", "panorama", "wildfire"],
        "name_tokens": ["panw", "palo", "firewall"],
    },
    "active_directory": {
        "product_codes": ["active_directory", "ldap", "windows"],
        "product_names": ["active directory", "ldap"],
        "name_tokens": ["ad", "active_directory", "ldap", "domain"],
    },
    "virustotalv3": {
        "product_codes": ["virustotal", "virustotalv3"],
        "product_names": ["virustotal"],
        "name_tokens": ["virustotal", "vt"],
    },
    "slack": {
        "product_codes": ["slack"],
        "product_names": ["slack"],
        "name_tokens": ["slack"],
    },
}


def assets_from_rest(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, list):
        return [a for a in resp if isinstance(a, dict)]
    if isinstance(resp, dict):
        for key in ("data", "assets", "items", "results"):
            data = resp.get(key)
            if isinstance(data, list):
                return [a for a in data if isinstance(a, dict)]
            if isinstance(data, dict) and data.get("id") is not None:
                return [data]
        if resp.get("id") is not None and resp.get("name"):
            return [resp]
    return []


def _fetch_assets_with_strategies(
    get_fn: Any,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    strategies: list[tuple[str, dict[str, Any] | None]] = [
        ("page_size=0", {"page_size": 0}),
        ("_page_size=0", {"_page_size": 0}),
        ("page=0 page_size=500", {"page": 0, "page_size": 500}),
        ("_page=0 _page_size=500", {"_page": 0, "_page_size": 500}),
    ]
    best: list[dict[str, Any]] = []
    for name, params in strategies:
        if params is None:
            continue
        ok, resp = get_fn(params)
        rows = assets_from_rest(resp) if ok else []
        if attempts_log is not None:
            attempts_log.append(f"GET asset {params} -> ok={ok} rows={len(rows)}")
        if len(rows) > len(best):
            best = rows
        if rows and len(rows) >= 10 and params.get("page_size") == 0:
            return rows
    return best


def fetch_configured_assets(
    request: Any | None = None,
    *,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List configured SOAR assets (GET /rest/asset) with pagination fallbacks."""

    if request is not None:
        def _get(params: dict[str, Any]) -> tuple[bool, Any]:
            ok, resp, _ = django_request_rest(request, "GET", "asset", params=params)
            return ok, resp

        return _fetch_assets_with_strategies(_get, attempts_log)

    def _get(params: dict[str, Any]) -> tuple[bool, Any]:
        ok, resp = phantom_rest_call("GET", "asset", None, params=params, request=None)
        return ok, resp

    return _fetch_assets_with_strategies(_get, attempts_log)


def extract_required_asset_keys(source: str) -> list[str]:
    """Unique scaffold asset keys referenced in phantom.act(..., assets=[...])."""
    seen: set[str] = set()
    ordered: list[str] = []
    for act in extract_phantom_acts(source or ""):
        for raw in act.get("assets") or []:
            key = str(raw).strip()
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def _asset_field(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _asset_matches_type(asset_record: dict[str, Any], required_key: str) -> bool:
    hints = ASSET_TYPE_HINTS.get(required_key, {})
    name = _normalize_token(_asset_field(asset_record, "name"))
    product_code = _normalize_token(
        _asset_field(asset_record, "product_code", "productCode", "app", "type")
    )
    product_name = ( _asset_field(asset_record, "product_name", "productName") or "").lower()
    req = _normalize_token(required_key)

    if name == req or name.startswith(f"{req}_") or req in name.split("_"):
        return True

    for code in hints.get("product_codes", []):
        if _normalize_token(code) == product_code or req in product_code:
            return True

    for pname in hints.get("product_names", []):
        if pname.lower() in product_name:
            return True

    for token in hints.get("name_tokens", []):
        tok = _normalize_token(token)
        if tok and (tok in name or tok in product_code):
            return True

    if not hints:
        return req in name or req in product_code or required_key.lower() in product_name

    return False


def _is_phantom_soar_asset(asset_record: dict[str, Any]) -> bool:
    """Splunk SOAR (phantom) connector asset — for add note, assign, etc."""
    if _is_mcp_bridge_like_asset(asset_record):
        return False
    product_code = _normalize_token(
        _asset_field(asset_record, "product_code", "productCode", "app", "type")
    )
    product_name = (_asset_field(asset_record, "product_name", "productName") or "").lower()
    return (
        product_code in {"phantom", "splunk_soar", "splunksoar"}
        or "splunk soar" in product_name
        or product_name == "phantom"
    )


def _is_playbook_builder_asset(asset_record: dict[str, Any]) -> bool:
    """Playbook Builder is an information-service asset — not for phantom.act add note / assign."""
    product_code = _normalize_token(
        _asset_field(asset_record, "product_code", "productCode", "app", "type")
    )
    product_name = (_asset_field(asset_record, "product_name", "productName") or "").lower()
    if "playbook_builder" in product_code or "playbook builder" in product_name:
        return True
    name = _normalize_token(_asset_field(asset_record, "name"))
    return name in {"mcpbridge", "playbook_builder", "soar_playbook_builder"}


def _is_mcp_bridge_like_asset(asset_record: dict[str, Any]) -> bool:
    name = (_asset_field(asset_record, "name") or "").lower()
    product = (_asset_field(asset_record, "product_name", "productName") or "").lower()
    return (
        _is_playbook_builder_asset(asset_record)
        or "mcp bridge" in name
        or "playbook builder" in product
    )


def _candidate_assets(required_key: str, configured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if required_key == "soar":
        pool = [a for a in configured if _is_phantom_soar_asset(a)]
        exact = [
            a for a in pool
            if _normalize_token(_asset_field(a, "name")) == "soar"
        ]
        if exact:
            return exact
        if len(pool) == 1:
            return pool
        if pool:
            return pool
        return []

    pool = configured

    exact = [
        a for a in pool
        if _normalize_token(_asset_field(a, "name")) == _normalize_token(required_key)
    ]
    if exact:
        return exact

    typed = [a for a in pool if _asset_matches_type(a, required_key)]
    if typed:
        return typed

    fuzzy = [
        a for a in pool
        if required_key.lower() in _asset_field(a, "name").lower()
        or required_key.lower() in _asset_field(a, "product_name", "productName").lower()
    ]
    return fuzzy


def parse_asset_defaults(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if v}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if v}
    except json.JSONDecodeError:
        pass
    out: dict[str, str] = {}
    for part in text.split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            if k.strip() and v.strip():
                out[k.strip()] = v.strip()
    return out


def apply_asset_map_to_source(source: str, asset_map: dict[str, str]) -> str:
    """Rewrite assets=[...] in Python source to use configured SOAR asset names."""

    if not asset_map:
        return source

    def _replace_assets(match: re.Match[str]) -> str:
        inner = match.group(1)
        names = re.findall(r"['\"]([^'\"]+)['\"]", inner)
        if not names:
            return match.group(0)
        mapped = [asset_map.get(n, n) for n in names]
        quoted = ", ".join(f'"{n}"' for n in mapped)
        return f"assets=[{quoted}]"

    return re.sub(r"assets=\[([^\]]+)\]", _replace_assets, source or "")


def _asset_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "name": _asset_field(record, "name"),
        "product_name": _asset_field(record, "product_name", "productName"),
        "product_code": _asset_field(record, "product_code", "productCode", "app", "type"),
    }


def resolve_asset_requirements(
    source: str,
    configured: list[dict[str, Any]],
    *,
    overrides: dict[str, str] | None = None,
    defaults: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build preflight result: required keys → configured asset names."""
    required_keys = extract_required_asset_keys(source)
    overrides = dict(overrides or {})
    defaults = dict(defaults or {})
    configured_by_name = {
        _asset_field(a, "name"): a for a in configured if _asset_field(a, "name")
    }

    requirements: list[dict[str, Any]] = []
    asset_map: dict[str, str] = {}
    missing: list[str] = []
    ambiguous: list[str] = []

    for key in required_keys:
        lane = ASSET_LANES.get(key, {}).get("lane", key)
        chosen = overrides.get(key) or defaults.get(key)
        candidates = _candidate_assets(key, configured)
        candidate_summaries = [_asset_summary(c) for c in candidates[:12]]

        status = "missing"
        resolved_name = ""
        resolution = ""

        if chosen:
            record = configured_by_name.get(chosen)
            if record and not (key == "soar" and not _is_phantom_soar_asset(record)):
                resolved_name = chosen
                status = "resolved"
                resolution = "override"
            else:
                status = "invalid_override" if key != "soar" else "missing"
                if key == "soar":
                    missing.append(key)
                    resolution = (
                        "no Splunk SOAR (phantom) asset — create one under Apps → Splunk SOAR"
                    )
                else:
                    resolution = f"override `{chosen}` not found on SOAR"
        elif len(candidates) == 1:
            resolved_name = _asset_field(candidates[0], "name")
            status = "resolved"
            resolution = "auto_single_match"
        elif len(candidates) > 1:
            status = "ambiguous"
            ambiguous.append(key)
            resolution = f"{len(candidates)} Splunk SOAR assets match"
        elif key == "soar":
            missing.append(key)
            resolution = "no Splunk SOAR (phantom) asset on SOAR"
        else:
            missing.append(key)
            resolution = "no configured asset on SOAR"

        if resolved_name:
            asset_map[key] = resolved_name

        requirements.append(
            {
                "key": key,
                "label": lane,
                "status": status,
                "resolved_name": resolved_name,
                "resolution": resolution,
                "candidates": candidate_summaries,
            }
        )

    ready = not missing and not ambiguous and all(
        r["status"] == "resolved" for r in requirements
    )

    return {
        "ready": ready,
        "required": required_keys,
        "requirements": requirements,
        "asset_map": asset_map,
        "missing": missing,
        "ambiguous": ambiguous,
        "configured_count": len(configured),
    }


def build_asset_preflight(
    source: str,
    request: Any | None = None,
    *,
    overrides: dict[str, str] | None = None,
    defaults: dict[str, str] | None = None,
    attempts_log: list[str] | None = None,
) -> dict[str, Any]:
    configured = fetch_configured_assets(request, attempts_log=attempts_log)
    result = resolve_asset_requirements(
        source, configured, overrides=overrides, defaults=defaults,
    )
    result["attempts"] = attempts_log or []
    return result


def preflight_message(preflight: dict[str, Any], *, base_url: str = "") -> str:
    if preflight.get("ready"):
        lines = ["**Asset preflight:** all integrations mapped."]
        for req in preflight.get("requirements") or []:
            if req.get("resolved_name"):
                lines.append(
                    f"- **{req.get('label', req.get('key'))}** → `{req['resolved_name']}` "
                    f"({req.get('resolution', 'resolved')})"
                )
        return "\n".join(lines)

    lines = [
        "**Asset preflight:** SOAR needs configured integrations before this playbook can run.",
        "",
    ]
    for req in preflight.get("requirements") or []:
        key = req.get("key", "")
        label = req.get("label", key)
        status = req.get("status", "")
        if status == "resolved":
            if req.get("resolution") == "builtin_soar":
                lines.append(f"- ✓ **{label}** → built-in SOAR (add note / assign)")
            elif req.get("resolved_name"):
                lines.append(f"- ✓ **{label}** → `{req.get('resolved_name')}`")
        elif status == "ambiguous":
            names = ", ".join(
                f"`{c.get('name')}`" for c in (req.get("candidates") or [])[:5]
            )
            lines.append(
                f"- ⚠ **{label}** — pick one: {names or '(none)'}"
            )
        else:
            hint = ASSET_TYPE_HINTS.get(key, {})
            product = (hint.get("product_names") or [label])[0]
            if key == "soar":
                lines.append(
                    f"- ✕ **{label}** — no Splunk SOAR (phantom) asset configured. "
                    "Create one under **Apps → Splunk SOAR → Asset** (name it `soar`, "
                    "set **phantom_server** to this instance), then re-import. "
                    "Do **not** use Playbook Builder / MCP bridge assets for add note / assign."
                )
            else:
                lines.append(
                    f"- ✕ **{label}** — no `{key}` asset on SOAR. "
                    f"Add a **{product.title()}** configuration under **Apps → Asset**, "
                    f"or set **asset_defaults** on the Playbook Builder asset."
                )

    if base_url:
        lines.append("")
        lines.append(f"Open **[Apps & assets]({base_url.rstrip('/')}/mission/#/apps)** to add missing configurations.")

    return "\n".join(lines)
