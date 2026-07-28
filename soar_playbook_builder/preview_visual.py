"""Rich preview: flow graph, Mermaid, and cross-system storyboard from playbook source."""

from __future__ import annotations

import re
from typing import Any

ASSET_LANES: dict[str, dict[str, str]] = {
    "splunk_enterprise": {"lane": "Splunk", "icon": "splunk"},
    "clearpass_cppm": {"lane": "ClearPass", "icon": "clearpass"},
    "ad_connector": {"lane": "Active Directory", "icon": "ad"},
    "panw": {"lane": "Palo Alto", "icon": "firewall"},
    "okta": {"lane": "Okta", "icon": "okta"},
    "servicenow": {"lane": "ServiceNow", "icon": "snow"},
    "soar": {"lane": "SOAR", "icon": "soar"},
    "slack": {"lane": "Slack", "icon": "slack"},
}

ACTION_LANE_DEFAULT = {"lane": "SOAR", "icon": "soar"}

DATAPATH_LABELS: dict[str, str] = {
    "artifact:*.cef.sourceAddress": "Source IP address",
    "artifact:*.cef.destinationAddress": "Destination IP address",
    "artifact:*.cef.destinationUserName": "Destination username",
    "artifact:*.cef.user": "Username",
    "artifact:*.cef.fileHash": "File hash (MD5)",
    "artifact:*.cef.fileHashSha256": "File hash (SHA-256)",
    "artifact:*.cef.requestURL": "Requested URL",
    "artifact:*.cef.requestUrl": "Requested URL",
    "artifact:*.cef.deviceCustomString1": "Device identifier (MAC / hostname)",
    "artifact:*.cef.deviceCustomString2": "Device posture / status",
    "artifact:*.cef.deviceCustomNumber1": "Risk score",
    "container:severity": "Case severity",
    "container:owner": "Case owner",
    "container:id": "Case ID",
}

ACTION_SUMMARIES: dict[str, str] = {
    "get user": "Look up the user in the identity provider",
    "disable user": "Disable the user account",
    "clear user sessions": "Clear active user sessions",
    "get endpoint": "Look up the endpoint in NAC / posture system",
    "quarantine device": "Quarantine the endpoint on the network",
    "update endpoint policy": "Apply quarantine / remediation policy to endpoint",
    "post data": "Write remediation event back to Splunk",
    "create ticket": "Create a ServiceNow incident",
    "update ticket": "Update the ServiceNow record",
    "block ip": "Block the IP address on the firewall",
    "query url": "Look up URL reputation",
    "file reputation": "Look up file hash reputation",
    "send message": "Send a Slack notification",
    "disable account": "Disable the Active Directory account",
}

_COLLECT2_RE = re.compile(
    r"phantom\.collect2\([^)]*datapath=\[(.*?)\]",
    re.DOTALL,
)
_ACT_FULL_RE = re.compile(
    r"phantom\.act\(\s*(?:action=\"([^\"]+)\"|['\"]([^'\"]+)['\"])"
    r"([^)]*)\)",
    re.DOTALL,
)
_NOTE_RE = re.compile(
    r"phantom\.add_note\(\s*[^)]*title=[\"']([^\"']+)[\"']",
    re.DOTALL,
)


def humanize_datapath(path: str) -> str:
    path = path.strip()
    if path in DATAPATH_LABELS:
        return DATAPATH_LABELS[path]
    if "action_result" in path:
        action_name = path.split(":")[0].replace("action_", "").replace("_", " ")
        field = path.split(".")[-1].replace("_", " ")
        return f"{field.title()} from {action_name.strip() or 'prior action'}"
    if path.startswith("artifact:") and "cef." in path:
        field = path.split("cef.", 1)[1]
        return field.replace("_", " ").title() + " (artifact)"
    if path.startswith("container:"):
        return path.split(":", 1)[1].replace("_", " ").title() + " (case)"
    return path


def humanize_action_summary(action: str) -> str:
    key = (action or "").strip().lower()
    if key in ACTION_SUMMARIES:
        return ACTION_SUMMARIES[key]
    return key.replace("_", " ").replace("-", " ").title() if key else "Run connector action"


def _parse_datapaths(raw: str) -> list[str]:
    return [p.strip() for p in re.findall(r'["\']([^"\']+)["\']', raw) if p.strip()]


def _summarize_collect(paths: list[str]) -> str:
    if not paths:
        return "Read artifact or case fields into playbook scope"
    if any("action_result" in p for p in paths):
        return "Read output from a previous action"
    if all(p.startswith("container:") for p in paths):
        return "Read case / container metadata"
    if len(paths) == 1:
        return f"Collect {humanize_datapath(paths[0])}"
    return f"Collect {len(paths)} fields from artifacts or case"


def _parse_act_tail(tail: str) -> dict[str, Any]:
    assets = re.findall(r"assets=\[([^\]]+)\]", tail, re.DOTALL)
    asset_list = re.findall(r"['\"]([^'\"]+)['\"]", assets[0]) if assets else []
    callback_match = re.search(r"callback=([A-Za-z_]\w*)", tail)
    name_match = re.search(r'name=["\']([^"\']+)["\']', tail)
    param_keys = re.findall(r'\{"([^"]+)":', tail)
    return {
        "assets": asset_list,
        "callback": callback_match.group(1) if callback_match else "",
        "name": name_match.group(1) if name_match else "",
        "parameters": param_keys,
    }


def _humanize_decision(test_source: str, func_name: str) -> tuple[str, str, list[str]]:
    cond = test_source.strip()
    branches: list[str] = []
    lower = cond.lower()
    summary = ""
    if "not success" in lower or "success is false" in lower:
        summary = "Previous connector action failed"
    elif "severity" in lower or "sev " in lower:
        summary = "Branch on case severity (high / critical vs lower)"
    elif "posture" in lower or "risk_score" in lower or "quarantine" in lower:
        summary = "Branch on endpoint posture or risk score before quarantine"
    elif "high_severit" in lower or "critical" in lower:
        summary = "Branch when severity is high or critical"
    else:
        cleaned = re.sub(r"\s+", " ", cond)
        summary = f"Conditional branch in {func_name.replace('_', ' ')}"
        if len(cleaned) <= 90:
            summary = cleaned
    detail = re.sub(r"\s+", " ", cond)
    if len(detail) > 120:
        detail = detail[:117] + "..."
    return summary, detail, branches


def _decision_events(source: str) -> list[tuple[int, dict[str, Any]]]:
    import ast

    events: list[tuple[int, dict[str, Any]]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return events

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith("decision_"):
            continue
        pos = source.find(f"def {node.name}")
        if pos < 0:
            pos = 0
        for child in ast.walk(node):
            if not isinstance(child, ast.If):
                continue
            test_src = (ast.get_source_segment(source, child.test) or "").strip()
            if not test_src:
                continue
            if_pos = source.find(test_src, pos)
            if if_pos < 0:
                if_pos = pos
            branches: list[str] = []
            for branch in (*child.body, *child.orelse):
                if isinstance(branch, ast.Return):
                    continue
                if isinstance(branch, ast.Expr) and isinstance(branch.value, ast.Call):
                    func = branch.value.func
                    if isinstance(func, ast.Name):
                        branches.append(func.id)
            summary, detail, _ = _humanize_decision(test_src, node.name)
            branch_hint = ""
            if branches:
                branch_hint = " → " + " / ".join(b.replace("_", " ") for b in branches[:2])
            events.append(
                (
                    if_pos,
                    {
                        "type": "decision",
                        "label": "Decision",
                        "summary": summary,
                        "detail": detail + branch_hint,
                        "function": node.name,
                        "branches": ",".join(branches),
                    },
                )
            )
            break  # primary branch per decision function
    return events


def build_rich_preview_blocks(source: str) -> list[dict[str, Any]]:
    """Build ordered preview blocks with human-readable summaries."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "start",
            "label": "Start",
            "summary": "Playbook starts on the SOAR container",
            "detail": "Triggers on_start(container) when the playbook runs",
        }
    ]
    events: list[tuple[int, dict[str, Any]]] = []

    for match in _COLLECT2_RE.finditer(source):
        paths = _parse_datapaths(match.group(1))
        fields = [humanize_datapath(p) for p in paths]
        events.append(
            (
                match.start(),
                {
                    "type": "collect",
                    "label": "Collect",
                    "summary": _summarize_collect(paths),
                    "detail": "Stores values for later actions and decisions",
                    "fields": "|".join(fields),
                    "datapaths": "|".join(paths),
                },
            )
        )

    for match in _ACT_FULL_RE.finditer(source):
        action = (match.group(1) or match.group(2) or "").strip()
        meta = _parse_act_tail(match.group(3) or "")
        asset = meta["assets"][0] if meta.get("assets") else ""
        param_hint = ""
        if meta.get("parameters"):
            param_hint = " using " + ", ".join(p.replace("_", " ") for p in meta["parameters"][:3])
        summary = humanize_action_summary(action)
        detail_parts = [f'Connector action "{action}"']
        if param_hint:
            detail_parts.append(param_hint.strip())
        if meta.get("callback"):
            detail_parts.append(f"then → {meta['callback'].replace('_', ' ')}")
        row: dict[str, Any] = {
            "type": "action",
            "label": "Action",
            "summary": summary,
            "detail": " · ".join(detail_parts),
            "action": action,
        }
        if asset:
            row["app"] = asset
            row["app_label"] = ASSET_LANES.get(asset, {}).get("lane", asset)
        if meta.get("name"):
            row["name"] = meta["name"]
        if meta.get("callback"):
            row["callback"] = meta["callback"]
        events.append((match.start(), row))

    for match in _NOTE_RE.finditer(source):
        title = match.group(1).strip()
        events.append(
            (
                match.start(),
                {
                    "type": "note",
                    "label": "Note",
                    "summary": f"Add analyst note: {title}",
                    "detail": "Documents findings on the SOAR case for reviewers",
                },
            )
        )

    events.extend(_decision_events(source))
    events.sort(key=lambda row: row[0])

    for _, row in events:
        blocks.append(row)

    blocks.append(
        {
            "type": "end",
            "label": "Finish",
            "summary": "Playbook completes",
            "detail": "Runs on_finish(container) and returns control to SOAR",
        }
    )
    return blocks


def extract_phantom_acts(source: str) -> list[dict[str, Any]]:
    acts: list[dict[str, Any]] = []
    for match in re.finditer(
        r"phantom\.act\(\s*(?:action=\"([^\"]+)\"|['\"]([^'\"]+)['\"])"
        r"([^)]*)\)",
        source,
        re.DOTALL,
    ):
        action = (match.group(1) or match.group(2) or "").strip()
        tail = match.group(3) or ""
        assets = re.findall(r"assets=\[([^\]]+)\]", tail, re.DOTALL)
        asset_list: list[str] = []
        if assets:
            asset_list = re.findall(r"['\"]([^'\"]+)['\"]", assets[0])
        name_match = re.search(r"name=\"([^\"]+)\"", tail)
        acts.append(
            {
                "action": action,
                "assets": asset_list,
                "name": name_match.group(1) if name_match else action,
            }
        )
    return acts


def extract_phantom_acts_with_context(source: str) -> list[dict[str, Any]]:
    """Each phantom.act with the enclosing Python function (COA functionName)."""
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return extract_phantom_acts(source)

    results: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        func_source = ast.get_source_segment(source, node) or ""
        for act in extract_phantom_acts(func_source):
            row = dict(act)
            row["function"] = node.name
            results.append(row)
    return results


def enrich_preview_blocks(
    source: str, preview: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Return rich preview blocks; rebuild from source when available."""
    if source:
        return build_rich_preview_blocks(source)
    return list(preview)


def preview_graph_from_source(
    source: str, preview: list[dict[str, str]]
) -> dict[str, Any]:
    blocks = enrich_preview_blocks(source, preview)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for i, block in enumerate(blocks):
        nid = f"n{i}"
        nodes.append(
            {
                "id": nid,
                "type": block.get("type", "action"),
                "label": block.get("label", "Step"),
                "detail": block.get("detail", ""),
                "app": block.get("app", ""),
                "app_label": block.get("app_label", ""),
            }
        )
        if i > 0:
            edges.append({"from": f"n{i - 1}", "to": nid})
    return {"nodes": nodes, "edges": edges}


def mermaid_from_graph(graph: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    for node in graph.get("nodes", []):
        nid = node["id"]
        label = node.get("label", "")
        detail = node.get("detail", "")
        app = node.get("app_label") or node.get("app") or ""
        text = label
        if detail and detail != label:
            text += "<br/><small>" + detail.replace('"', "'")[:40] + "</small>"
        if app:
            text += "<br/><small>" + app.replace('"', "'") + "</small>"
        ntype = node.get("type", "")
        if ntype == "decision":
            lines.append(f'    {nid}{{{{"{text}"}}}}')
        elif ntype == "start":
            lines.append(f'    {nid}(["{text}"])')
        elif ntype == "end":
            lines.append(f'    {nid}(("{text}"))')
        else:
            lines.append(f'    {nid}["{text}"]')
    for edge in graph.get("edges", []):
        lines.append(f'    {edge["from"]} --> {edge["to"]}')
    return "\n".join(lines)


def storyboard_from_source(source: str) -> list[dict[str, str]]:
    """Cross-system swimlane steps for demo storytelling."""
    steps: list[dict[str, str]] = [
        {
            "lane": "Splunk / Case",
            "title": "Trigger & artifacts",
            "detail": "Notable or event opens SOAR container; CEF fields on artifacts",
        }
    ]
    if "phantom.collect2" in source:
        steps.append(
            {
                "lane": "SOAR",
                "title": "Collect datapaths",
                "detail": "phantom.collect2 reads IP, user, risk, posture from artifacts",
            }
        )

    for act in extract_phantom_acts(source):
        asset = act["assets"][0] if act.get("assets") else ""
        meta = ASSET_LANES.get(asset, ACTION_LANE_DEFAULT)
        steps.append(
            {
                "lane": meta["lane"],
                "title": act.get("action") or "Action",
                "detail": f"Asset: {asset or 'soar'} · block {act.get('name', '')}",
            }
        )

    if re.search(r"\bif\b", source):
        steps.append(
            {
                "lane": "SOAR",
                "title": "Decision",
                "detail": "Branch on risk, posture, or action success before next step",
            }
        )

    steps.append(
        {
            "lane": "SOAR",
            "title": "Finish",
            "detail": "on_finish — close loop, debug summary, case ready for analyst",
        }
    )
    return steps


def soar_playbook_links(
    base_url: str,
    playbook_id: int | str | None,
    *,
    playbook_name: str | None = None,
    playbook_slug: str | None = None,
    playbook_display_name: str | None = None,
    playbook_search: str | None = None,
    playbook_record: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Deep links on the same SOAR host as the sidecar."""
    from urllib.parse import quote

    from draft_import import playbook_search_term, slug_from_label

    base = (base_url or "").rstrip("/")
    links = {
        "playbooks_list": f"{base}/playbooks",
        "mission": f"{base}/mission",
        "home": base + "/",
    }
    record_name = str((playbook_record or {}).get("name") or playbook_name or "")
    search_term = (playbook_search or "").strip() or playbook_search_term(
        (playbook_slug or "").strip(),
        (playbook_display_name or "").strip(),
        record_name,
    )
    if search_term:
        links["playbooks_search"] = f"{base}/playbooks?search={quote(search_term)}"
        links["open"] = links["playbooks_search"]
    else:
        links["open"] = links["playbooks_list"]
    display_term = (playbook_display_name or "").strip()
    if display_term and display_term.lower() != search_term.lower():
        links["playbooks_search_display"] = (
            f"{base}/playbooks?search={quote(display_term)}"
        )
    if playbook_id is not None and str(playbook_id).strip():
        pid = str(playbook_id).strip()
        links["playbook"] = f"{base}/playbook/{pid}"
        links["vpe"] = f"{base}/playbook/{pid}?editor=visual"
        links["python"] = f"{base}/playbook/{pid}?editor=python"
        links["open"] = links["vpe"]
        links["playbook_alt"] = f"{base}/mission/#/playbook/{pid}"
        if playbook_name:
            links["playbook_name"] = (playbook_display_name or playbook_name).strip()
    return links


def attach_visual_preview(payload: dict[str, Any], base_url: str = "") -> dict[str, Any]:
    """Add preview_graph, mermaid, storyboard, soar_links to a scaffold-shaped payload."""
    source = payload.get("source") or ""
    preview = payload.get("preview") or []
    if source and preview:
        graph = preview_graph_from_source(source, preview)
        payload["preview"] = enrich_preview_blocks(source, preview)
        payload["preview_graph"] = graph
        payload["mermaid"] = mermaid_from_graph(graph)
        payload["storyboard"] = storyboard_from_source(source)
    pb_id = payload.get("playbook_id")
    if base_url and pb_id:
        record = payload.get("playbook_record")
        payload["soar_links"] = soar_playbook_links(
            base_url,
            pb_id,
            playbook_name=payload.get("playbook_name"),
            playbook_slug=payload.get("playbook_slug"),
            playbook_display_name=payload.get("playbook_display_name")
            or payload.get("pattern_label"),
            playbook_search=payload.get("playbook_search"),
            playbook_record=record if isinstance(record, dict) else None,
        )
    return payload
