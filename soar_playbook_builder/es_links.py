"""Build Splunk ES / Mission Control URLs for sidecar round-trip links."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode


def normalize_es_web_url(raw: str | None) -> str:
    """Strip trailing slashes from configured ES web base (e.g. https://es.example.com:8000)."""
    return (raw or "").strip().rstrip("/")


def build_mission_control_url(
    es_web_url: str,
    *,
    event_id: str | None = None,
    investigation_id: str | None = None,
    rule_name: str | None = None,
) -> str | None:
    """Deep link to ES Mission Control / ess_investigation for a notable event."""
    base = normalize_es_web_url(es_web_url)
    if not base:
        return None

    if investigation_id:
        params = {
            "earliest": "-7d@h",
            "latest": "now",
            "investigation_id": investigation_id,
        }
        if event_id:
            params["event_id"] = event_id
        qs = urlencode(params, quote_via=quote)
        return (
            f"{base}/en-US/app/SplunkEnterpriseSecuritySuite/ess_investigation?{qs}"
        )

    if event_id:
        params = {
            "earliest": "-7d@h",
            "latest": "now",
            "event_id": event_id,
        }
        if rule_name:
            params["rule_name"] = rule_name
        qs = urlencode(params, quote_via=quote)
        return (
            f"{base}/en-US/app/SplunkEnterpriseSecuritySuite/ess_investigation?{qs}"
        )

    return f"{base}/en-US/app/SplunkEnterpriseSecuritySuite/missioncontrol"


def build_incident_review_url(es_web_url: str, *, event_id: str | None = None) -> str | None:
    """Fallback link to ES Incident Review when event_id is present."""
    base = normalize_es_web_url(es_web_url)
    if not base or not event_id:
        return None
    params = urlencode({"form.event_id": event_id}, quote_via=quote)
    return f"{base}/en-US/app/SplunkEnterpriseSecuritySuite/incident_review?{params}"


def build_es_back_links(
    es_web_url: str,
    *,
    event_id: str | None = None,
    rule_name: str | None = None,
    investigation_id: str | None = None,
) -> dict[str, str]:
    """Return labeled ES links for sidecar header (Mission Control preferred)."""
    out: dict[str, str] = {}
    mc = build_mission_control_url(
        es_web_url,
        event_id=event_id,
        investigation_id=investigation_id,
        rule_name=rule_name,
    )
    if mc:
        out["mission_control"] = mc
    ir = build_incident_review_url(es_web_url, event_id=event_id)
    if ir:
        out["incident_review"] = ir
    base = normalize_es_web_url(es_web_url)
    if base:
        out["es_home"] = f"{base}/en-US/app/SplunkEnterpriseSecuritySuite/missioncontrol"
    return out


def attach_es_links(ctx: dict[str, Any], es_web_url: str | None) -> None:
    """Mutate investigation context with es_links when es_web_url is configured."""
    if not normalize_es_web_url(es_web_url):
        return
    links = build_es_back_links(
        es_web_url or "",
        event_id=str(ctx.get("event_id") or "") or None,
        rule_name=str(ctx.get("rule_name") or "") or None,
        investigation_id=str(ctx.get("investigation_id") or "") or None,
    )
    if links:
        ctx["es_links"] = links
        ctx["es_back_url"] = links.get("mission_control") or links.get("incident_review") or links.get("es_home")
