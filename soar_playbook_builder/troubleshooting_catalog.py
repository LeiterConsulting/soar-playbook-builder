"""Offline troubleshooting catalog — maps errors and symptoms to fix steps."""

from __future__ import annotations

import re
from typing import Any

CatalogEntry = dict[str, Any]

TROUBLESHOOTING_ENTRIES: list[CatalogEntry] = [
    {
        "id": "templates_only",
        "title": "Templates only mode (AI bridge offline)",
        "severity": "info",
        "match_patterns": [
            r"templates only",
            r"ai bridge offline",
            r"mcp bridge unreachable",
            r"could not reach the mcp",
            r"using offline builder",
        ],
        "symptom": "Sidecar shows Templates only or build uses offline keyword matching.",
        "cause": "SOAR cannot reach the MCP bridge URL, or no LLM is configured. This is normal in air-gapped deployments.",
        "fix_steps": [
            "Continue using Pattern library and Example prompts marked Works offline — no AI required.",
            "Optional: leave mcp_bridge_url empty on the asset to avoid connectivity warnings.",
            "If you later enable AI: start MCP on the bridge host, verify curl health from the SOAR server, set mcp_bridge_url on the asset.",
        ],
        "verify": "Click a template example (e.g. Okta Failed Logins) — preview and Import should work without AI connected.",
    },
    {
        "id": "mcp_bridge_unreachable",
        "title": "MCP bridge unreachable from SOAR",
        "severity": "warn",
        "match_patterns": [
            r"mcp bridge unreachable",
            r"mcp bridge http \d+",
            r"mcp bridge error at",
            r"curl .*health",
        ],
        "symptom": "Build or chat returns MCP bridge unreachable; health check fails from SOAR.",
        "cause": "Network path from SOAR app process to mcp_bridge_url is blocked, tunnel down, or URL wrong.",
        "fix_steps": [
            "On the SOAR server run: curl -sS <mcp_bridge_url>/../health (or /agent/health).",
            "Confirm MCP listens on the host SOAR can reach (not only localhost on your laptop).",
            "Fix SSH tunnel / firewall: SOAR must reach port 8003 (or your configured port).",
            "Use Pattern library → Use template — works without MCP.",
        ],
        "verify": "Asset Test connectivity succeeds, or sidecar Build works via template without bridge.",
    },
    {
        "id": "build_timeout",
        "title": "Build timed out or HTTP 500",
        "severity": "error",
        "match_patterns": [
            r"timed out after",
            r"server error \(500\)",
            r"handler may have timed out",
            r"http 500",
        ],
        "symptom": "Build button spins then fails with timeout or HTTP 500.",
        "cause": "SOAR handler timeout (~30s) while waiting for MCP/Ollama, or unhandled Python error.",
        "fix_steps": [
            "Use Pattern library dropdown + Use template instead of open-ended Build.",
            "Upgrade to app v2.10.0+ (keyword templates run on SOAR before MCP).",
            "If using AI: ensure Ollama responds within 120s or use a faster model.",
            "Check SOAR connector logs for traceback after reinstall.",
        ],
        "verify": "Select ServiceNow P1 or Okta Failed Logins → Use template — preview appears in under 5 seconds.",
    },
    {
        "id": "needs_assets",
        "title": "Configure integrations before import",
        "severity": "error",
        "match_patterns": [
            r"needs_assets",
            r"configure integrations before import",
            r"missing configuration",
            r"needs_assets",
            r"asset preflight",
        ],
        "symptom": "Import blocked; integration panel shows missing or ambiguous assets.",
        "cause": "Playbook references asset keys (okta, servicenow, etc.) not mapped to configured SOAR assets.",
        "fix_steps": [
            "Apps → install the integration app (e.g. Okta) and create an asset with a known name (e.g. okta).",
            "On the Playbook Builder asset, set asset_defaults JSON: {\"okta\": \"okta\"} (match your asset name).",
            "In the integration panel below, pick the correct asset for each row, then Import again.",
            "Run Test connectivity on each integration asset.",
        ],
        "verify": "Asset preflight panel shows all integrations green before Import.",
    },
    {
        "id": "okta_asset_missing",
        "title": "Okta asset missing or not mapped",
        "severity": "error",
        "match_patterns": [
            r"okta.*missing",
            r"\"okta\"",
            r"assets=\[\"okta\"\]",
            r"no asset.*okta",
        ],
        "symptom": "Okta playbook import or run fails; preflight shows Okta missing.",
        "cause": "No Okta asset on SOAR or asset_defaults does not map key okta to your asset name.",
        "fix_steps": [
            "Install Splunk SOAR Okta app from Apps catalog.",
            "Create asset named okta (or note your name).",
            "Set asset_defaults on Playbook Builder asset: {\"okta\": \"<your_okta_asset_name>\"}.",
            "Re-run Use template for Okta Failed Logins, confirm preflight, then Import.",
        ],
        "verify": "Preflight shows Okta ✓; VPE action blocks show okta asset selected.",
    },
    {
        "id": "vpe_invalid_datapath",
        "title": "Invalid datapath in Visual Playbook Editor",
        "severity": "error",
        "match_patterns": [
            r"invalid datapath",
            r"datapath.*invalid",
            r"blank block editor",
            r"empty.*block.*click",
        ],
        "symptom": "VPE shows invalid datapath or empty editor when clicking a block.",
        "cause": "COA graph nodes did not match Python function names (fixed in v2.9.5+).",
        "fix_steps": [
            "Delete the broken playbook in SOAR Playbooks.",
            "Upgrade Playbook Builder to v2.10.0+ and re-import from sidecar.",
            "Do not hand-edit COA JSON — re-import from template source.",
        ],
        "verify": "Click each action block in VPE — editor shows Python function body.",
    },
    {
        "id": "vpe_soar_missing_config",
        "title": "SOAR connector Missing Configuration in VPE",
        "severity": "error",
        "match_patterns": [
            r"soar \(3\).*missing",
            r"phantom\.act.*assets=\[\"soar\"\]",
            r"splunk soar.*missing configuration",
        ],
        "symptom": "VPE shows soar (3) Missing Configuration on note/assign blocks.",
        "cause": "Old templates used phantom.act against a soar asset; fixed in v2.9.4+ using phantom.add_note / set_owner.",
        "fix_steps": [
            "Upgrade to v2.9.4+ and re-import playbook from sidecar template.",
            "Remove dependency on Splunk SOAR (phantom) app for notes and assignment.",
        ],
        "verify": "Re-imported playbook has no phantom.act(..., assets=[\"soar\"]) in source.",
    },
    {
        "id": "import_failed",
        "title": "Import to SOAR failed",
        "severity": "error",
        "match_patterns": [
            r"import failed",
            r"import_playbook.*fail",
            r"sync failed",
            r"auto-import failed",
            r"scm sync",
        ],
        "symptom": "Import button fails; red sync error or import log shows failure.",
        "cause": "Packaging error, SCM permissions, duplicate playbook name, or asset preflight block.",
        "fix_steps": [
            "Read Import log steps — note which phase failed (assets, package, upload, scm, resolve).",
            "Fix asset preflight first if assets step failed.",
            "Delete duplicate playbook with same slug in SOAR Playbooks, then re-import.",
            "Check SOAR admin permissions for playbook import.",
            "If SOAR reports Python 2.7, stop: this app supports SOAR 8.5 / Python 3.13 only. Use Splunk's supported platform migration workflow.",
        ],
        "verify": "Sidecar shows ✓ Synced with playbook id; Open in SOAR opens VPE.",
    },
    {
        "id": "okta_get_user_failed",
        "title": "Okta get user action failed at runtime",
        "severity": "error",
        "match_patterns": [
            r"okta get user failed",
            r"get user.*failed",
            r"assigned tier2.*okta",
        ],
        "symptom": "Playbook runs but assigns tier2 with Okta get user failed.",
        "cause": "Container missing user artifact, wrong CEF field, empty username parameter, or Okta token/scope issue.",
        "fix_steps": [
            "Ensure container has artifact with cef.user or cef.destinationUserName (Failed Logins use case).",
            "For manual test: create container, add artifact type user with user field set.",
            "Verify Okta asset API token and scopes (okta.users.read, okta.sessions.manage as needed).",
            "Re-import v2.10.0+ Okta template — get user passes collected username.",
        ],
        "verify": "Run playbook on test container with user artifact; action_get_user succeeds in SOAR.",
    },
    {
        "id": "es_soar_export_missing",
        "title": "ES Mission Control / SOAR export not configured",
        "severity": "warn",
        "match_patterns": [
            r"mission control.*empty",
            r"response tab empty",
            r"export to soar",
            r"es.*soar.*pair",
            r"no soar export",
        ],
        "symptom": "ES Incident Review or Mission Control has no Export to SOAR; Response tab empty.",
        "cause": "ES–SOAR pairing and response plans not configured in lab.",
        "fix_steps": [
            "ES → Configure → Incident Review → Splunk SOAR Integration — pair SOAR instance.",
            "Configure notable export / response plan for your use case.",
            "Lab fallback: create SOAR container manually, add user artifact, run playbook from Playbooks tab.",
            "See docs/FAILED_LOGINS_QUICK_START.md for manual container test recipe.",
        ],
        "verify": "Notable appears in SOAR as container, or manual container runs playbook end-to-end.",
    },
    {
        "id": "sidecar_blank_404",
        "title": "Sidecar blank page or 404",
        "severity": "error",
        "match_patterns": [
            r"sidecar.*404",
            r"blank page",
            r"wrong url path",
            r"missing widget asset",
        ],
        "symptom": "Playbook Builder page does not load or shows 404.",
        "cause": "Wrong handler URL (package name vs directory slug) or app not installed/enabled.",
        "fix_steps": [
            "Run ./scripts/print_sidecar_url.sh for correct URL (uses directory from /rest/app).",
            "URL format: /rest/handler/<directory>/<asset>/chat",
            "Reinstall soar_playbook_builder.tgz and enable app in SOAR Apps.",
            "Hard-refresh browser (Ctrl+Shift+R).",
        ],
        "verify": "Sidecar loads with Pattern library and Example prompts visible.",
    },
    {
        "id": "no_draft",
        "title": "Build a playbook first",
        "severity": "info",
        "match_patterns": [
            r"build a playbook first",
            r"no draft to import",
            r"no playbook source",
        ],
        "symptom": "Import disabled or message says build first.",
        "cause": "No source code in preview — template not generated yet.",
        "fix_steps": [
            "Pick a scenario in Guided wizard or Pattern library → Use template.",
            "Or click an Example prompt, then wait for Code tab to show Python.",
            "Then click Import.",
        ],
        "verify": "Code tab shows def on_start(container): before Import.",
    },
    {
        "id": "empty_response",
        "title": "Empty response from SOAR",
        "severity": "error",
        "match_patterns": [
            r"empty response from soar",
            r"builder returned no preview",
        ],
        "symptom": "Build returns no preview or message.",
        "cause": "Old app version, handler error, or message did not match build intent.",
        "fix_steps": [
            "Upgrade to v2.10.0+.",
            "Use scaffold command: type scaffold okta-idp-response in chat.",
            "Use Pattern library + Use template.",
        ],
        "verify": "Template generates preview blocks and Python source.",
    },
    {
        "id": "unknown_pattern",
        "title": "Unknown playbook pattern",
        "severity": "info",
        "match_patterns": [
            r"unknown pattern",
        ],
        "symptom": "scaffold or pattern name not recognized.",
        "cause": "Typo or pattern not in library.",
        "fix_steps": [
            "Use Pattern library dropdown for valid names.",
            "Try: hello, okta-idp-response, failed-logins-okta, es-notable-response, servicenow-incident, clearpass-quarantine.",
            "Type scaffold <pattern-id> exactly as listed.",
        ],
        "verify": "Use template succeeds for selected pattern.",
    },
]


def _compile_patterns() -> list[tuple[CatalogEntry, re.Pattern[str]]]:
    compiled: list[tuple[CatalogEntry, re.Pattern[str]]] = []
    for entry in TROUBLESHOOTING_ENTRIES:
        combined = "|".join(f"(?:{p})" for p in entry.get("match_patterns", []))
        if combined:
            compiled.append((entry, re.compile(combined, re.IGNORECASE)))
    return compiled


_COMPILED = _compile_patterns()


def _entry_payload(entry: CatalogEntry) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "title": entry["title"],
        "severity": entry.get("severity", "info"),
        "symptom": entry.get("symptom", ""),
        "cause": entry.get("cause", ""),
        "fix_steps": list(entry.get("fix_steps", [])),
        "verify": entry.get("verify", ""),
    }


def match_troubleshooting(
    text: str,
    *,
    status: str | None = None,
    extra: str | None = None,
) -> dict[str, Any] | None:
    """Return best matching troubleshooting entry for error text or status."""
    haystack = " ".join(filter(None, [text or "", status or "", extra or ""]))
    if not haystack.strip():
        return None

    if status == "needs_assets":
        for entry in TROUBLESHOOTING_ENTRIES:
            if entry["id"] == "needs_assets":
                return _entry_payload(entry)

    best: tuple[int, CatalogEntry] | None = None
    for entry, pattern in _COMPILED:
        matches = pattern.findall(haystack)
        if not matches:
            continue
        score = len(matches) + (2 if entry.get("severity") == "error" else 0)
        if best is None or score > best[0]:
            best = (score, entry)

    if best:
        return _entry_payload(best[1])
    return None


def search_troubleshooting(query: str | None = None) -> list[dict[str, Any]]:
    """Search catalog by keyword; empty query returns all entries."""
    q = (query or "").strip().lower()
    if not q:
        return [_entry_payload(e) for e in TROUBLESHOOTING_ENTRIES]

    results: list[tuple[int, CatalogEntry]] = []
    for entry in TROUBLESHOOTING_ENTRIES:
        blob = " ".join(
            [
                entry.get("id", ""),
                entry.get("title", ""),
                entry.get("symptom", ""),
                entry.get("cause", ""),
                " ".join(entry.get("fix_steps", [])),
                entry.get("verify", ""),
            ]
        ).lower()
        if q in blob:
            results.append((blob.index(q), entry))
            continue
        for word in q.split():
            if len(word) >= 3 and word in blob:
                results.append((blob.index(word), entry))
                break

    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for _, entry in sorted(results, key=lambda row: row[0]):
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        ordered.append(_entry_payload(entry))
    return ordered


def attach_troubleshooting(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Attach troubleshooting block to API payload when error or needs_assets."""
    if not isinstance(payload, dict):
        return payload or {}

    status = str(payload.get("status") or "")
    parts = [
        str(payload.get("error") or ""),
        str(payload.get("import_error") or ""),
        str(payload.get("content") or ""),
        str(payload.get("hint") or ""),
    ]
    if payload.get("import_steps"):
        for step in payload["import_steps"]:
            if isinstance(step, dict):
                parts.append(str(step.get("detail") or ""))
                parts.append(str(step.get("label") or ""))

    text = "\n".join(parts)
    entry = match_troubleshooting(text, status=status)
    if entry:
        payload["troubleshooting"] = entry
    return payload


def troubleshooting_api_payload(query: str | None = None) -> dict[str, Any]:
    entries = search_troubleshooting(query)
    return {"status": "success", "entries": entries, "count": len(entries)}
