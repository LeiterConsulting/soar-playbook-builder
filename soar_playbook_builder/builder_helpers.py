"""Playbook builder helpers for SOAR sidecar (no MCP dependency on SOAR)."""

from __future__ import annotations

import ast
import re
from typing import Any

from preview_visual import attach_visual_preview, soar_playbook_links

SCAFFOLDS: dict[str, str] = {
    "hello": '''import phantom.app as phantom


def on_start(container):
    phantom.debug("Playbook started on container %s" % container["id"])


def on_finish(container):
    phantom.debug("Playbook finished")
''',
    "es-notable-response": '''import phantom.app as phantom

PLAYBOOK_LABEL = "es_notable_response"


def on_start(container):
    source_ips = phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.sourceAddress"],
    )
    phantom.debug("Notable response — source IPs: %s" % source_ips)
    phantom.add_note(
        container=container,
        title="ES notable response",
        content="ES notable response playbook ran",
    )
    on_finish(container)


def on_finish(container):
    phantom.debug("ES notable response complete")
''',
    "indicator-enrichment": '''import phantom.app as phantom


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.fileHash", "artifact:*.cef.fileHashSha256"],
    )
    phantom.add_note(
        container=container,
        title="Indicator enrichment",
        content="IOCs collected — use VirusTotal template or wire reputation action.",
    )
    on_finish(container)


def on_finish(container):
    phantom.debug("Enrichment chain complete")
''',
    "clearpass-quarantine": '''import phantom.app as phantom

QUARANTINE_RISK_THRESHOLD = 70
QUARANTINE_POSTURE_STATES = ["FAILED", "UNHEALTHY", "UNKNOWN"]
QUARANTINE_ROLE = "Quarantine"
HEC_INDEX = "clearpass_remediation"


def on_start(container):
    phantom.debug("[ClearPass Quarantine] container %s" % container["id"])
    phantom.collect2(
        container=container,
        datapath=[
            "artifact:*.cef.sourceAddress",
            "artifact:*.cef.deviceCustomString1",
            "artifact:*.cef.deviceCustomString2",
            "artifact:*.cef.deviceCustomNumber1",
        ],
    )
    get_endpoint(container)


def get_endpoint(container, ip=None, mac=None):
    phantom.act(
        action="get endpoint",
        parameters=[{"ip_address": ip}],
        assets=["clearpass_cppm"],
        callback=decision_quarantine,
        name="action_get_endpoint",
        container=container,
    )


def decision_quarantine(action=None, success=None, container=None, results=None, handle=None):
    posture = phantom.collect2(
        container=container,
        datapath=["action_get_endpoint:action_result.data.*.posture_status"],
    )
    risk = phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.deviceCustomNumber1"],
    )
    posture_value = posture[0][0] if posture and posture[0] else "UNKNOWN"
    risk_score = int(risk[0][0]) if risk and risk[0] and risk[0][0] else 0
    if posture_value.upper() in QUARANTINE_POSTURE_STATES or risk_score >= QUARANTINE_RISK_THRESHOLD:
        quarantine_device(container)
    else:
        on_finish(container)


def quarantine_device(container):
    phantom.act(
        action="quarantine device",
        parameters=[{"reason": "Splunk SOAR automated quarantine"}],
        assets=["clearpass_cppm"],
        callback=update_endpoint_policy,
        name="action_quarantine_device",
        container=container,
    )


def update_endpoint_policy(action=None, success=None, container=None, results=None, handle=None):
    phantom.act(
        action="update endpoint policy",
        parameters=[{"new_role": QUARANTINE_ROLE}],
        assets=["clearpass_cppm"],
        callback=writeback_to_splunk,
        name="action_update_policy",
        container=container,
    )


def writeback_to_splunk(action=None, success=None, container=None, results=None, handle=None):
    phantom.act(
        action="post data",
        parameters=[{"index": HEC_INDEX, "source": "splunk_soar:clearpass_remediation"}],
        assets=["splunk_enterprise"],
        callback=on_finish,
        name="action_writeback_splunk",
        container=container,
    )


def on_finish(container, summary=None):
    phantom.debug("[ClearPass Quarantine] complete for container %s" % container["id"])
''',
    "servicenow-incident": '''import phantom.app as phantom

INCIDENT_TABLE = "incident"
PRIORITY_P1 = "1"


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["container:severity", "container:owner"],
    )
    create_incident(container)


def create_incident(container):
    description = "SOAR container %s — review and assign analyst." % container["id"]
    phantom.act(
        "create ticket",
        parameters=[{
            "table": INCIDENT_TABLE,
            "short_description": "SOAR P1 — container %s" % container["id"],
            "description": description,
            "urgency": PRIORITY_P1,
            "impact": PRIORITY_P1,
        }],
        assets=["servicenow"],
        callback=wait_for_assignment,
        name="action_create_incident",
        container=container,
    )


def wait_for_assignment(action=None, success=None, container=None, results=None, handle=None):
    phantom.add_note(
        container=container,
        title="ServiceNow P1",
        content="Waiting for analyst assignment on ServiceNow ticket.",
    )
    on_finish(container)


def on_finish(container, summary=None):
    phantom.debug("[ServiceNow P1] workflow complete for container %s" % container["id"])
''',
    "okta-idp-response": '''import phantom.app as phantom

PLAYBOOK_LABEL = "okta_idp_response"
HIGH_SEVERITIES = ("high", "critical")


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=[
            "artifact:*.cef.destinationUserName",
            "artifact:*.cef.user",
            "container:severity",
        ],
    )
    lookup_okta_user(container)


def lookup_okta_user(container):
    username_rows = phantom.collect2(
        container=container,
        datapath=[
            "artifact:*.cef.destinationUserName",
            "artifact:*.cef.user",
        ],
    )
    username = username_rows[0][0] if username_rows and username_rows[0] else ""
    phantom.act(
        "get user",
        parameters=[{"username": username}],
        assets=["okta"],
        callback=decision_severity,
        name="action_get_user",
        container=container,
    )


def decision_severity(action=None, success=None, container=None, results=None, handle=None):
    if not success:
        assign_tier2(container, reason="Okta get user failed")
        return
    severity = phantom.collect2(
        container=container,
        datapath=["container:severity"],
    )
    sev = (severity[0][0] if severity and severity[0] else "").lower()
    okta_id = phantom.collect2(
        container=container,
        datapath=["action_get_user:action_result.data.*.id"],
    )
    okta_user_id = okta_id[0][0] if okta_id and okta_id[0] else "unknown"
    if sev in HIGH_SEVERITIES:
        remediate_okta_user(container, okta_user_id)
    else:
        add_info_note(container, okta_user_id)


def remediate_okta_user(container, okta_user_id):
    phantom.act(
        "clear user sessions",
        parameters=[{"user_id": okta_user_id}],
        assets=["okta"],
        callback=disable_okta_user,
        name="action_clear_sessions",
        container=container,
    )


def disable_okta_user(action=None, success=None, container=None, results=None, handle=None):
    okta_id = phantom.collect2(
        container=container,
        datapath=["action_get_user:action_result.data.*.id"],
    )
    okta_user_id = okta_id[0][0] if okta_id and okta_id[0] else ""
    phantom.act(
        "disable user",
        parameters=[{"user_id": okta_user_id}],
        assets=["okta"],
        callback=add_remediation_note,
        name="action_disable_user",
        container=container,
    )


def add_remediation_note(action=None, success=None, container=None, results=None, handle=None):
    okta_id = phantom.collect2(
        container=container,
        datapath=["action_get_user:action_result.data.*.id"],
    )
    okta_user_id = okta_id[0][0] if okta_id and okta_id[0] else "unknown"
    phantom.add_note(
        container=container,
        title="Okta remediation",
        content="Okta user remediated. Okta user ID: %s" % okta_user_id,
    )
    on_finish(container)


def add_info_note(container, okta_user_id):
    phantom.add_note(
        container=container,
        title="Okta IDP response",
        content="Okta user resolved (informational). Okta user ID: %s" % okta_user_id,
    )
    on_finish(container)


def assign_tier2(container, reason=""):
    phantom.set_owner(container=container, role="tier2")
    phantom.debug("[Okta IDP] assigned tier2: %s" % reason)
    on_finish(container)


def on_finish(container, summary=None):
    phantom.debug("[Okta IDP response] complete for container %s" % container["id"])
''',
    "phishing-enrichment": '''import phantom.app as phantom


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.requestURL", "artifact:*.cef.requestUrl"],
    )
    phantom.add_note(
        container=container,
        title="Phishing enrichment",
        content="Enrich request URL — wire URL reputation action for your environment.",
    )
    on_finish(container)


def on_finish(container):
    phantom.debug("[Phishing enrichment] complete")
''',
    "insider-threat-ad": '''import phantom.app as phantom

HIGH_SEVERITIES = ("high", "critical")


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.user", "container:severity"],
    )
    decision_contain(container)


def decision_contain(container):
    severity = phantom.collect2(container=container, datapath=["container:severity"])
    sev = (severity[0][0] if severity and severity[0] else "").lower()
    if sev in HIGH_SEVERITIES:
        disable_ad_user(container)
    else:
        phantom.add_note(
            container=container,
            title="Insider threat review",
            content="Medium/low severity — analyst review recommended.",
        )
        on_finish(container)


def disable_ad_user(container):
    username_rows = phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.user"],
    )
    username = username_rows[0][0] if username_rows and username_rows[0] else ""
    phantom.act(
        "disable account",
        parameters=[{"username": username}],
        assets=["active_directory"],
        callback=on_finish,
        name="action_disable_ad",
        container=container,
    )


def on_finish(container, summary=None):
    phantom.debug("[Insider threat AD] complete for container %s" % container["id"])
''',
    "panw-block-ip": '''import phantom.app as phantom

HEC_INDEX = "firewall_remediation"


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.destinationAddress"],
    )
    block_ip(container)


def block_ip(container):
    phantom.act(
        "block ip",
        parameters=[{}],
        assets=["panw"],
        callback=verify_block,
        name="action_block_ip",
        container=container,
    )


def verify_block(action=None, success=None, container=None, results=None, handle=None):
    phantom.act(
        "list blocked ips",
        parameters=[{}],
        assets=["panw"],
        callback=writeback_splunk,
        name="action_list_blocked",
        container=container,
    )


def writeback_splunk(action=None, success=None, container=None, results=None, handle=None):
    phantom.act(
        "post data",
        parameters=[{"index": HEC_INDEX, "source": "splunk_soar:firewall_remediation"}],
        assets=["splunk_enterprise"],
        callback=on_finish,
        name="action_writeback_splunk",
        container=container,
    )


def on_finish(container, summary=None):
    phantom.debug("[PANW block] complete for container %s" % container["id"])
''',
    "virustotal-enrichment": '''import phantom.app as phantom

VT_MALICIOUS_THRESHOLD = 1


def on_start(container):
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.fileHash", "artifact:*.cef.fileHashSha256"],
    )
    query_virustotal(container)


def query_virustotal(container):
    hash_rows = phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.fileHash", "artifact:*.cef.fileHashSha256"],
    )
    file_hash = hash_rows[0][0] if hash_rows and hash_rows[0] else ""
    phantom.act(
        "file reputation",
        parameters=[{"hash": file_hash}],
        assets=["virustotalv3"],
        callback=decision_verdict,
        name="action_vt_query",
        container=container,
    )


def decision_verdict(action=None, success=None, container=None, results=None, handle=None):
    if not success:
        phantom.add_note(
            container=container,
            title="VirusTotal verdict",
            content="VT query failed — review action results and investigate manually.",
        )
        on_finish(container)
        return

    malicious_count = _first_int(
        phantom.collect2(
            container=container,
            datapath=[
                "action_vt_query:action_result.summary.malicious",
                "action_vt_query:action_result.data.*.attributes.last_analysis_stats.malicious",
            ],
        )
    )
    suspicious_count = _first_int(
        phantom.collect2(
            container=container,
            datapath=[
                "action_vt_query:action_result.summary.suspicious",
                "action_vt_query:action_result.data.*.attributes.last_analysis_stats.suspicious",
            ],
        )
    )
    hash_rows = phantom.collect2(
        container=container,
        datapath=["action_vt_query:action_result.parameter.hash"],
    )
    file_hash = hash_rows[0][0] if hash_rows and hash_rows[0] else "unknown"
    verdict = "malicious" if malicious_count >= VT_MALICIOUS_THRESHOLD else "clean"
    phantom.add_note(
        container=container,
        title="VirusTotal verdict",
        content=(
            "Hash: %s — malicious=%s suspicious=%s — verdict=%s"
            % (file_hash, malicious_count, suspicious_count, verdict)
        ),
    )
    if malicious_count >= VT_MALICIOUS_THRESHOLD:
        close_malicious_container(container, file_hash, malicious_count)
    else:
        on_finish(container)


def close_malicious_container(container, file_hash, malicious_count):
    phantom.comment(
        container=container,
        comment=(
            "Auto-closed: VirusTotal reported %s malicious detection(s) for hash %s"
            % (malicious_count, file_hash)
        ),
    )
    phantom.set_status(container=container, status="closed")
    on_finish(container)


def _first_int(rows):
    if not rows:
        return 0
    for row in rows:
        if not row:
            continue
        for val in row:
            if val is None or val == "":
                continue
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return 0


def on_finish(container, summary=None):
    phantom.debug("[VirusTotal enrichment] complete for container %s" % container["id"])
''',
}

BUILDER_STEPS: list[dict[str, Any]] = [
    {
        "id": "gather",
        "title": "Gather",
        "summary": "Define trigger, label, and data you need from the case.",
        "prompts": [
            "What label triggers ClearPass quarantine? (clearpass_nac)",
            "Which CEF fields hold IP, MAC, posture, and risk score?",
            "What assets do I need — clearpass_cppm and splunk_enterprise?",
            "What happens when posture is FAILED or risk >= 70?",
        ],
    },
    {
        "id": "propose",
        "title": "Propose",
        "summary": "Sketch blocks: Start → Collect → Decision → Actions → Finish.",
        "prompts": [
            "Outline blocks for ClearPass NAC quarantine playbook",
            "Explain datapaths for action_get_endpoint results",
            "Why do we need a decision block before quarantine?",
            "What is the HEC writeback step for?",
        ],
    },
    {
        "id": "scaffold",
        "title": "Scaffold",
        "summary": "Generate starter Python from a pattern (preview updates on the right).",
        "prompts": [
            "scaffold clearpass-quarantine",
            "scaffold es-notable-response",
            "scaffold hello",
            "lesson 05-packaging-import",
        ],
    },
    {
        "id": "validate",
        "title": "Validate",
        "summary": "Check syntax, datapaths, and classic playbook structure.",
        "prompts": [
            "validate current preview",
            "quiz packaging",
            "lesson 05-packaging-import",
            "What is wrong with source_address datapath?",
        ],
    },
    {
        "id": "import",
        "title": "Import",
        "summary": "Package as .tgz and import into SOAR 8.x (use Cursor MCP or REST).",
        "prompts": [
            "How do I package a .py playbook for SOAR 8.x?",
            "lesson 05-packaging-import",
            "What causes NoneType error on import?",
            "Steps to import via soar_import_playbook in Cursor",
        ],
    },
    {
        "id": "sync",
        "title": "Sync VPE",
        "summary": "Poll for changes after import, then refresh Visual Playbook Editor.",
        "prompts": [
            "Poll VPE for changes",
            "When do I refresh the Visual Editor?",
            "lesson 06-debug-and-test",
        ],
    },
]

PATTERN_LABELS = {
    "hello": "Hello World",
    "es-notable-response": "ES Notable Response",
    "indicator-enrichment": "Indicator Enrichment (IOCs)",
    "virustotal-enrichment": "VirusTotal File Hash",
    "clearpass-quarantine": "Aruba ClearPass NAC Quarantine",
    "servicenow-incident": "ServiceNow P1 Incident",
    "okta-idp-response": "Okta IDP Response",
    "failed-logins-okta": "Access — Excessive Failed Logins (Okta)",
    "phishing-enrichment": "Phishing URL Enrichment",
    "insider-threat-ad": "Insider Threat — Disable AD User",
    "panw-block-ip": "Palo Alto Block IP",
    "panw-block-stub": "Palo Alto Block IP",
}

# Failed-logins variant — same automation as okta-idp-response, distinct playbook label
SCAFFOLDS["failed-logins-okta"] = SCAFFOLDS["okta-idp-response"].replace(
    'PLAYBOOK_LABEL = "okta_idp_response"',
    'PLAYBOOK_LABEL = "excessive_failed_logins"',
)

PATTERN_ALIASES: dict[str, str] = {
    "hello-world": "hello",
    "es-notable": "es-notable-response",
    "es": "es-notable-response",
    "enrichment": "indicator-enrichment",
    "clearpass": "clearpass-quarantine",
    "nac-quarantine": "clearpass-quarantine",
    "aruba-clearpass": "clearpass-quarantine",
    "okta": "okta-idp-response",
    "failed-logins": "failed-logins-okta",
    "excessive-failed-logins": "failed-logins-okta",
    "access-failed-logins": "failed-logins-okta",
    "nnsa-failed-logins": "failed-logins-okta",
    "panw": "panw-block-ip",
    "panw-block-stub": "panw-block-ip",
    "palo-alto": "panw-block-ip",
    "virustotal": "virustotal-enrichment",
    "vt": "virustotal-enrichment",
}


def resolve_pattern_key(pattern: str) -> str:
    key = pattern.strip().lower().replace("_", "-")
    return PATTERN_ALIASES.get(key, key)


def analyze_playbook(source: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    score = 100
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "valid_python": False,
            "score": 0,
            "findings": [{"level": "error", "message": f"Syntax error: {exc}"}],
            "functions": [],
        }

    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if "on_start" not in functions:
        score -= 25
        findings.append({"level": "error", "message": "Missing on_start(container)"})
    if "on_finish" not in functions:
        score -= 10
        findings.append({"level": "warn", "message": "Missing on_finish(container)"})
    if re.search(r"artifact:\*\.cef\.source_address", source):
        score -= 15
        findings.append(
            {"level": "error", "message": "Use sourceAddress (camelCase), not source_address"}
        )

    datapaths = re.findall(r'["\'](artifact:[^"\']+|container:[^"\']+)["\']', source)
    return {
        "valid_python": True,
        "score": max(0, score),
        "findings": findings,
        "functions": functions,
        "datapaths": datapaths,
        "collect2_count": source.count("phantom.collect2"),
        "act_count": source.count("phantom.act"),
        "line_count": len(source.splitlines()),
    }


def preview_blocks_from_source(source: str) -> list[dict[str, str]]:
    """Approximate VPE block flow from classic Python playbook source."""
    from preview_visual import build_rich_preview_blocks

    return build_rich_preview_blocks(source)


def scaffold_pattern(pattern: str, org_registry: Any | None = None) -> dict[str, Any]:
    key = resolve_pattern_key(pattern)
    source = None
    if org_registry is not None:
        source = org_registry.scaffold_source(key)
    if not source:
        source = SCAFFOLDS.get(key)
    if not source:
        return {
            "status": "error",
            "error": f"Unknown pattern '{pattern}'. Try: {', '.join(SCAFFOLDS)}",
        }

    analysis = analyze_playbook(source)
    label = key
    if org_registry is not None:
        label = org_registry.label_for(key) or label
    label = PATTERN_LABELS.get(key, label)
    result = {
        "status": "success",
        "pattern": key,
        "pattern_label": label,
        "source": source,
        "preview": preview_blocks_from_source(source),
        "analysis": analysis,
        "content": (
            f"Scaffolded **{label}** playbook.\n\n"
            f"- {analysis['line_count']} lines · score {analysis['score']}/100\n"
            f"- {analysis['collect2_count']} collect · {analysis['act_count']} actions\n\n"
            "Use **Blocks**, **Diagram**, or **Story** tabs on the right. Open in VPE after import."
        ),
    }
    return attach_visual_preview(result)


def builder_steps_payload() -> dict[str, Any]:
    from pattern_catalog import list_patterns_payload

    payload = list_patterns_payload()
    payload["steps"] = BUILDER_STEPS
    payload["patterns_legacy"] = PATTERN_LABELS
    return payload


def parse_builder_action(message: str) -> str | None:
    lower = message.strip().lower()
    if lower.startswith("scaffold "):
        return lower.replace("scaffold ", "", 1).strip()
    if lower.startswith("pattern "):
        return lower.replace("pattern ", "", 1).strip()
    return None
