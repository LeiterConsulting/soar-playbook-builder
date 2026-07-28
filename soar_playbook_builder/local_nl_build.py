"""Offline NL build fallback on SOAR when MCP bridge is unreachable."""

from __future__ import annotations

import re
from typing import Any

from builder_helpers import (
    SCAFFOLDS,
    analyze_playbook,
    preview_blocks_from_source,
    resolve_pattern_key,
    scaffold_pattern,
)

_BUILD_VERBS = ("build", "create", "generate", "make", "design", "write", "author", "scaffold")
_PLAYBOOK_NOUNS = ("playbook", "automation", "response", "workflow", "coa", "firewall")

PATTERN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "clearpass-quarantine": ("clearpass", "quarantine", "nac", "posture", "aruba", "cppm"),
    "es-notable-response": ("es notable", "notable response", "mission control"),
    "indicator-enrichment": ("indicator enrichment", "filehash", "file hash", "ioc"),
    "virustotal-enrichment": ("virustotal", "file hash", "filehash", "vt hash", "verdict"),
    "phishing-enrichment": ("phishing", "requesturl", "malicious url"),
    "insider-threat-ad": ("insider", "disable ad", "disable user", "ueba", "insider_threat", "active directory"),
    "hello": ("hello world", "minimal playbook"),
    "servicenow-incident": ("servicenow", "service now", "snow incident", "p1 incident"),
    "okta-idp-response": ("okta", "identity provider", "idp", "get user", "clear session", "destinationusername"),
    "failed-logins-okta": (
        "failed login",
        "failed logins",
        "excessive failed",
        "access - excessive",
        "brute force",
        "password spray",
    ),
}

# Integrations / workflow shapes outside shipped scaffolds — defer to LLM or generic stub.
_CUSTOM_WORKFLOW_HINTS: tuple[str, ...] = (
    "pagerduty",
    "microsoft teams",
    " ms teams",
    "post to teams",
    "teams channel",
    "jira ticket",
    "open a jira",
    "fortinet",
    "azure ad",
    "cisco ise",
    "defender",
    "impossible travel",
    "analyst approv",
    "wait for approv",
    "hold execution",
    "until approv",
    "approval gate",
    "before running any containment",
    "three branches",
    "elif ",
)


def should_defer_to_llm(message: str) -> bool:
    """True when the prompt likely needs custom generation, not a catalog keyword scaffold."""
    lower = message.strip().lower()
    if not lower:
        return False
    if any(hint in lower for hint in _CUSTOM_WORKFLOW_HINTS):
        return True
    # Long multi-step asks often mention several vendors; avoid greedy single-template match.
    vendor_terms = (
        "okta",
        "servicenow",
        "snow",
        "slack",
        "palo alto",
        "panw",
        "clearpass",
        "virustotal",
        "pagerduty",
        "teams",
        "jira",
        "fortinet",
        "azure",
        "cisco",
        "defender",
    )
    hits = sum(1 for term in vendor_terms if term in lower)
    return hits >= 3


def is_build_intent(message: str) -> bool:
    lower = message.strip().lower()
    if not lower or lower.startswith(("lesson ", "quiz ", "explain ")):
        return False
    if lower.startswith("scaffold "):
        return True
    has_verb = any(v in lower for v in _BUILD_VERBS)
    has_noun = any(n in lower for n in _PLAYBOOK_NOUNS)
    return has_verb and (has_noun or len(lower.split()) >= 8)


def _pattern_available(key: str, org_registry: Any | None) -> bool:
    if key in SCAFFOLDS:
        return True
    return bool(org_registry and key in org_registry.scaffolds)


def match_pattern(message: str, org_registry: Any | None = None) -> str | None:
    lower = message.strip().lower()
    if lower.startswith("scaffold "):
        raw = lower.replace("scaffold ", "", 1).strip().replace("_", "-")
        key = resolve_pattern_key(raw)
        return key if _pattern_available(key, org_registry) else None
    keywords = dict(PATTERN_KEYWORDS)
    if org_registry is not None:
        keywords.update(org_registry.nl_keywords)
    scores: dict[str, int] = {}
    for pattern, kws in keywords.items():
        score = sum(1 for kw in kws if kw in lower)
        if score:
            scores[pattern] = score
    if "palo alto" in lower or "panw" in lower or "block ip" in lower:
        scores["panw-block-ip"] = max(scores.get("panw-block-ip", 0), 2)
    if "okta" in lower and any(k in lower for k in ("failed", "login", "brute", "idp")):
        scores["failed-logins-okta"] = max(scores.get("failed-logins-okta", 0), 3)
    return max(scores, key=scores.get) if scores else None


def _generic_stub(message: str) -> str:
    snippet = re.sub(r"\s+", " ", message.replace('"', "'"))[:100]
    return f'''import phantom.app as phantom

# Offline stub (MCP bridge unavailable). Refine after reconnect.


def on_start(container):
    phantom.debug("Build request: {snippet}")
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.sourceAddress"],
    )
    phantom.add_note(
        container=container,
        title="Playbook stub",
        content="Playbook stub — customize actions",
    )
    on_finish(container)


def on_finish(container):
    phantom.debug("Playbook finished")
'''


def _bridge_note(bridge_error: str | None) -> str:
    if not bridge_error:
        return (
            "\n\n_(Using offline builder — SOAR could not reach the MCP bridge. "
            "Send a new prompt after fixing connectivity.)_"
        )
    return (
        f"\n\n**Why offline?** SOAR could not reach the MCP agent bridge:\n`{bridge_error}`\n\n"
        "Verify health **from the SOAR server** (same path the connector uses): "
        "`curl <your-mcp_bridge_url>/../health` — see docs/MCP_INTEGRATION.md."
    )


def try_local_build(
    message: str,
    bridge_error: str | None = None,
    org_registry: Any | None = None,
) -> dict[str, Any] | None:
    """Pattern match + stub generation without MCP."""
    if not is_build_intent(message):
        return None

    note = _bridge_note(bridge_error)
    pattern = match_pattern(message, org_registry=org_registry)
    if pattern and _pattern_available(pattern, org_registry) and not should_defer_to_llm(message):
        result = scaffold_pattern(pattern, org_registry=org_registry)
        if result.get("status") == "success":
            result["content"] = str(result.get("content", "")) + note
            result["offline_mode"] = True
            result["suggested_pattern"] = pattern
        return result

    from preview_visual import attach_visual_preview

    source = _generic_stub(message)
    analysis = analyze_playbook(source)
    result = {
        "status": "success",
        "pattern": "nl-generated",
        "pattern_label": "Generated playbook (offline)",
        "source": source,
        "preview": preview_blocks_from_source(source),
        "analysis": analysis,
        "offline_mode": True,
        "llm_fallback": True,
        "content": (
            "Generated a **starter playbook** offline.\n\n"
            f"- Score {analysis['score']}/100"
            + note
        ),
    }
    return attach_visual_preview(result)
