"""Single source of truth for playbook template metadata (UI + tests)."""

from __future__ import annotations

from typing import Any

from runtime_fixtures import RUNTIME_FIXTURES

# Tier metadata aligned with runtime_fixtures.py and Splunk MCP enablement policy hints.
DESTRUCTIVE_ACTIONS: dict[str, list[str]] = {
    "failed-logins-okta": ["clear user sessions", "disable user"],
    "insider-threat-ad": ["disable AD account"],
    "clearpass-quarantine": ["quarantine endpoint"],
    "panw-block-ip": ["block IP address"],
}

NL_KEYWORDS: dict[str, list[str]] = {
    "failed-logins-okta": ["failed login", "excessive failed", "brute force", "okta"],
    "okta-idp-response": ["okta", "idp", "get user"],
    "insider-threat-ad": ["insider", "ueba", "disable ad"],
    "es-notable-response": ["es notable", "notable response", "mission control"],
    "clearpass-quarantine": ["clearpass", "quarantine", "nac"],
    "panw-block-ip": ["palo alto", "panw", "block ip"],
    "servicenow-incident": ["servicenow", "p1 incident"],
    "virustotal-enrichment": ["virustotal", "file hash"],
    "phishing-enrichment": ["phishing", "malicious url"],
    "indicator-enrichment": ["indicator", "ioc", "file hash"],
    "hello": ["hello world"],
}


def pattern_tier(pattern_id: str) -> str:
    fix = RUNTIME_FIXTURES.get(pattern_id)
    return fix.tier if fix else "safe"


def pattern_meta(pattern_id: str, org_registry: Any | None = None) -> dict[str, Any]:
    if org_registry is not None:
        from custom_templates import merged_catalog_by_id

        row = merged_catalog_by_id(org_registry).get(pattern_id, {})
    else:
        row = catalog_by_id().get(pattern_id, {})
    if row.get("org"):
        tier = str(row.get("tier") or "integration")
        return {
            **row,
            "tier": tier,
            "requires_confirm": tier == "destructive",
            "destructive_actions": row.get("destructive_actions") or [],
            "nl_keywords": row.get("nl_keywords") or [],
        }
    tier = pattern_tier(pattern_id)
    return {
        **row,
        "tier": tier,
        "requires_confirm": tier == "destructive",
        "destructive_actions": DESTRUCTIVE_ACTIONS.get(pattern_id, []),
        "nl_keywords": NL_KEYWORDS.get(pattern_id, []),
    }

# category → display order in template dropdown
PATTERN_CATALOG: list[dict[str, Any]] = [
    {
        "id": "hello",
        "label": "Hello World",
        "category": "Getting started",
        "description": "Minimal smoke test — no integrations required.",
        "integrations": [],
        "offline": True,
    },
    {
        "id": "failed-logins-okta",
        "label": "Excessive Failed Logins (Okta)",
        "category": "Identity & access",
        "description": "Access — Excessive Failed Logins: Okta lookup, session clear, disable on high severity.",
        "integrations": ["okta"],
        "offline": True,
    },
    {
        "id": "okta-idp-response",
        "label": "Okta IDP Response",
        "category": "Identity & access",
        "description": "Okta user lookup with severity-based remediation.",
        "integrations": ["okta"],
        "offline": True,
    },
    {
        "id": "insider-threat-ad",
        "label": "Insider Threat — AD Disable",
        "category": "Identity & access",
        "description": "Disable Active Directory account on high/critical UEBA severity.",
        "integrations": ["active_directory"],
        "offline": True,
    },
    {
        "id": "es-notable-response",
        "label": "ES Notable Response",
        "category": "Splunk ES",
        "description": "Collect source IP, add analyst note — pair with ES export when ready.",
        "integrations": [],
        "offline": True,
    },
    {
        "id": "clearpass-quarantine",
        "label": "Aruba ClearPass Quarantine",
        "category": "Network & NAC",
        "description": "Quarantine endpoint when posture fails or risk score ≥ 70.",
        "integrations": ["clearpass_cppm", "splunk_enterprise"],
        "offline": True,
    },
    {
        "id": "panw-block-ip",
        "label": "Palo Alto Block IP",
        "category": "Network & NAC",
        "description": "Block destination IP, verify block, write remediation to Splunk HEC.",
        "integrations": ["panw", "splunk_enterprise"],
        "offline": True,
    },
    {
        "id": "servicenow-incident",
        "label": "ServiceNow P1 Incident",
        "category": "ITSM & ticketing",
        "description": "Create P1 incident from container severity and owner.",
        "integrations": ["servicenow"],
        "offline": True,
    },
    {
        "id": "indicator-enrichment",
        "label": "Indicator Enrichment (IOCs)",
        "category": "Threat enrichment",
        "description": "Collect file hashes from artifacts — wire VT/reputation action for your environment.",
        "integrations": ["virustotalv3"],
        "offline": True,
    },
    {
        "id": "virustotal-enrichment",
        "label": "VirusTotal File Hash",
        "category": "Threat enrichment",
        "description": "Query VirusTotal for file hashes, add verdict note, close container when malicious.",
        "integrations": ["virustotalv3"],
        "offline": True,
    },
    {
        "id": "phishing-enrichment",
        "label": "Phishing URL Enrichment",
        "category": "Threat enrichment",
        "description": "Collect request URL from artifacts — wire URL reputation for production.",
        "integrations": [],
        "offline": True,
    },
]


def catalog_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in PATTERN_CATALOG}


def list_patterns_payload(org_registry: Any | None = None) -> dict[str, Any]:
    """API payload for sidecar template dropdown."""
    all_rows = list(PATTERN_CATALOG)
    if org_registry is not None:
        all_rows.extend(org_registry.catalog_rows)
    by_category: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        cat = row.get("category") or "Other"
        meta = pattern_meta(row["id"], org_registry=org_registry)
        by_category.setdefault(cat, []).append(
            {
                "id": row["id"],
                "label": row["label"],
                "description": row.get("description", ""),
                "integrations": row.get("integrations") or [],
                "offline": row.get("offline", True),
                "tier": meta.get("tier", "safe"),
                "requires_confirm": meta.get("requires_confirm", False),
                "destructive_actions": meta.get("destructive_actions") or [],
                "org": bool(row.get("org")),
            }
        )
    enriched = [pattern_meta(row["id"], org_registry=org_registry) for row in all_rows]
    org_count = org_registry.count if org_registry else 0
    return {
        "status": "success",
        "patterns": enriched,
        "by_category": by_category,
        "count": len(all_rows),
        "shipped_count": len(PATTERN_CATALOG),
        "org_template_count": org_count,
        "org_errors": list(org_registry.errors) if org_registry else [],
        "org_warnings": list(org_registry.warnings) if org_registry else [],
    }


def catalog_ids() -> list[str]:
    return [row["id"] for row in PATTERN_CATALOG]
