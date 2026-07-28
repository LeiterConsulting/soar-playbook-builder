"""Hydrate sidecar context from SOAR container + ES/Mission Control URL hints."""

from __future__ import annotations

import json
from typing import Any

from local_nl_build import match_pattern
from es_links import attach_es_links
from soar_rest import phantom_rest_call


def suggest_pattern_from_rule(rule_name: str) -> str | None:
    """Map ES rule / notable name to a Playbook Builder template id."""
    if not rule_name:
        return None
    lower = rule_name.lower()
    if any(k in lower for k in ("failed login", "failed logon", "brute force", "password spray")):
        return "failed-logins-okta"
    if "insider" in lower or "ueba" in lower:
        return "insider-threat-ad"
    if "phish" in lower or "malicious url" in lower:
        return "phishing-enrichment"
    if "virustotal" in lower or "file hash" in lower or "malware hash" in lower:
        return "virustotal-enrichment"
    if "clearpass" in lower or "quarantine" in lower or "nac" in lower:
        return "clearpass-quarantine"
    if "palo alto" in lower or "panw" in lower or "block ip" in lower:
        return "panw-block-ip"
    if "servicenow" in lower or "incident" in lower:
        return "servicenow-incident"
    if "notable" in lower or "es premier" in lower or "mission control" in lower:
        return "es-notable-response"
    return match_pattern(f"build playbook for {rule_name}")


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


def _fetch_container(container_id: int, request: Any | None) -> tuple[dict[str, Any] | None, str | None]:
    ok, resp = phantom_rest_call("GET", f"container/{container_id}", request=request)
    if not ok:
        return None, str(resp)
    rows = _rows_from_rest(resp)
    if rows:
        return rows[0], None
    if isinstance(resp, dict) and resp.get("id"):
        return resp, None
    return None, f"Container {container_id} not found"


def _fetch_artifacts(container_id: int, request: Any | None) -> tuple[list[dict[str, Any]], str | None]:
    ok, resp = phantom_rest_call(
        "GET",
        "artifact",
        params={"_page_size": 100, "_filter": f'container_id="{container_id}"'},
        request=request,
    )
    if not ok:
        return [], str(resp)
    return _rows_from_rest(resp), None


def _cef_summary(artifacts: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    keys = (
        "user",
        "destinationUserName",
        "sourceAddress",
        "destinationAddress",
        "fileHash",
        "requestURL",
        "src",
    )
    for art in artifacts:
        cef = art.get("cef") if isinstance(art.get("cef"), dict) else {}
        for key in keys:
            val = cef.get(key)
            if val and key not in out:
                out[key] = str(val)
    return out


def _hydrate_sample_context(
    sample: dict[str, Any],
    *,
    event_id: str | None,
    rule_name: str | None,
    investigation_id: str | None,
    es_web_url: str | None,
) -> dict[str, Any]:
    """Build investigation context from a sample/demo case row."""
    cid = sample.get("id")
    eff_event = event_id or str(sample.get("event_id") or "")
    eff_rule = rule_name or str(sample.get("rule_name") or "")
    ctx: dict[str, Any] = {
        "status": "success",
        "source": "sample",
        "container_id": cid,
        "event_id": eff_event,
        "rule_name": eff_rule,
        "investigation_id": investigation_id or "",
        "container": {
            "id": cid,
            "name": sample.get("name") or f"Sample case {cid}",
            "severity": sample.get("severity") or "",
            "status": sample.get("status") or "open",
            "label": sample.get("label") or "",
        },
        "artifact_count": 2,
        "cef": {},
    }
    summary = str(sample.get("summary") or "")
    if "jdoe" in summary:
        ctx["cef"]["user"] = "jdoe"
    if "10.0.0.5" in summary:
        ctx["cef"]["sourceAddress"] = "10.0.0.5"
    suggested = suggest_pattern_from_rule(eff_rule or str(sample.get("name") or ""))
    if suggested:
        ctx["suggested_pattern"] = suggested
        if suggested == "failed-logins-okta":
            ctx["wizard_scenario_id"] = "failed-logins-okta"
    ctx["message"] = _format_context_message(ctx) + " (sample case)"
    attach_es_links(ctx, es_web_url)
    return ctx


def hydrate_investigation_context(
    request: Any,
    *,
    container_id: int | None = None,
    event_id: str | None = None,
    rule_name: str | None = None,
    investigation_id: str | None = None,
    es_web_url: str | None = None,
    sample_cases_json: str | None = None,
) -> dict[str, Any]:
    """Build investigation context for sidecar boot and template pre-select."""
    ctx: dict[str, Any] = {
        "status": "success",
        "source": "soar",
        "container_id": container_id,
        "event_id": event_id or "",
        "rule_name": rule_name or "",
        "investigation_id": investigation_id or "",
    }

    suggested = suggest_pattern_from_rule(rule_name or "")
    if suggested:
        ctx["suggested_pattern"] = suggested

    if container_id is None:
        ctx["message"] = (
            "No case linked — pick a case below, use get sidecar url with container_id, "
            "or see How to run on a case."
        )
        attach_es_links(ctx, es_web_url)
        return ctx

    from case_catalog import lookup_sample_case

    sample = lookup_sample_case(container_id, sample_cases_json)
    if sample:
        return _hydrate_sample_context(
            sample,
            event_id=event_id,
            rule_name=rule_name,
            investigation_id=investigation_id,
            es_web_url=es_web_url,
        )

    container, err = _fetch_container(container_id, request)
    if err or not container:
        ctx["status"] = "partial"
        ctx["error"] = err or "container lookup failed"
        return ctx

    ctx["container"] = {
        "id": container.get("id"),
        "name": container.get("name"),
        "severity": container.get("severity"),
        "status": container.get("status"),
        "label": container.get("label"),
    }

    artifacts, art_err = _fetch_artifacts(container_id, request)
    if art_err:
        ctx["artifacts_error"] = art_err
    ctx["artifact_count"] = len(artifacts)
    ctx["cef"] = _cef_summary(artifacts)

    if not rule_name and container.get("name"):
        maybe = suggest_pattern_from_rule(str(container.get("name")))
        if maybe:
            ctx["suggested_pattern"] = maybe

    if not ctx.get("suggested_pattern"):
        user = ctx.get("cef", {}).get("user") or ctx.get("cef", {}).get("destinationUserName")
        if user:
            ctx["suggested_pattern"] = "failed-logins-okta"

    severity = str(container.get("severity") or "").lower()
    if severity in ("high", "critical") and ctx.get("suggested_pattern") == "failed-logins-okta":
        ctx["wizard_scenario_id"] = "failed-logins-okta"

    ctx["message"] = _format_context_message(ctx)
    attach_es_links(ctx, es_web_url)
    return ctx


def _format_context_message(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    cid = ctx.get("container_id")
    if cid:
        parts.append(f"Container **{cid}**")
    if ctx.get("rule_name"):
        parts.append(f"rule `{ctx['rule_name']}`")
    if ctx.get("event_id"):
        parts.append(f"event `{ctx['event_id']}`")
    if ctx.get("investigation_id"):
        parts.append(f"investigation `{ctx['investigation_id']}`")
    cef = ctx.get("cef") or {}
    if cef.get("user"):
        parts.append(f"user `{cef['user']}`")
    if cef.get("sourceAddress"):
        parts.append(f"src `{cef['sourceAddress']}`")
    if ctx.get("suggested_pattern"):
        parts.append(f"suggested template **{ctx['suggested_pattern']}**")
    return " · ".join(parts) if parts else "Investigation context loaded"


def parse_context_ids(request: Any, post_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read context ids from POST body or GET query."""
    post_body = post_body or {}

    def _get(key: str) -> str | None:
        if key in post_body and post_body.get(key) not in (None, ""):
            return str(post_body[key])
        raw = getattr(request, "GET", {}).get(key)
        return str(raw) if raw not in (None, "") else None

    out: dict[str, Any] = {}
    for key in ("event_id", "rule_name", "investigation_id"):
        val = _get(key)
        if val:
            out[key] = val

    raw_cid = _get("container_id")
    if raw_cid:
        try:
            out["container_id"] = int(raw_cid)
        except (TypeError, ValueError):
            out["container_id"] = raw_cid
    return out
