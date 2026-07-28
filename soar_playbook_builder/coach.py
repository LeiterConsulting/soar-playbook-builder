"""Coach lane — case-aware template suggestions (deterministic L0)."""

from __future__ import annotations

from typing import Any

from investigation_context import hydrate_investigation_context, parse_context_ids, suggest_pattern_from_rule
from coach_case_intel import coach_case_intel
from pattern_catalog import catalog_by_id


def _pattern_label(pattern_id: str | None) -> str:
    if not pattern_id:
        return ""
    row = catalog_by_id().get(pattern_id) or {}
    return str(row.get("label") or pattern_id)


def _case_summary(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    container = ctx.get("container") if isinstance(ctx.get("container"), dict) else {}
    if container.get("id"):
        parts.append(f"Case **{container['id']}**")
    if container.get("name"):
        parts.append(str(container["name"]))
    if container.get("severity"):
        parts.append(f"severity {container['severity']}")
    if ctx.get("rule_name"):
        parts.append(f"rule `{ctx['rule_name']}`")
    cef = ctx.get("cef") if isinstance(ctx.get("cef"), dict) else {}
    if cef.get("user"):
        parts.append(f"user {cef['user']}")
    if cef.get("sourceAddress"):
        parts.append(f"src {cef['sourceAddress']}")
    if ctx.get("artifact_count"):
        parts.append(f"{ctx['artifact_count']} artifacts")
    return " · ".join(parts) if parts else "No case linked yet."


def coach_suggest_payload(
    request: Any,
    cfg: dict[str, Any],
    post_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic coach response for Respond tab (no LLM)."""
    post_body = post_body or {}
    ids = parse_context_ids(request, post_body)
    ctx = hydrate_investigation_context(
        request,
        es_web_url=cfg.get("es_web_url"),
        sample_cases_json=cfg.get("sample_cases_json"),
        **ids,
    )
    rule = str(ctx.get("rule_name") or ids.get("rule_name") or "")
    suggested = ctx.get("suggested_pattern") or suggest_pattern_from_rule(rule)
    label = _pattern_label(suggested)
    summary = _case_summary(ctx)
    cid = ctx.get("container_id") or ids.get("container_id")
    try:
        cid_int = int(cid) if cid is not None else None
    except (TypeError, ValueError):
        cid_int = None
    intel = coach_case_intel(cid_int, request=request)

    lines = ["**Response coach**", "", summary]
    if intel.get("run_count"):
        lines.append("")
        lines.append(f"**Recent playbook runs on case:** {intel['run_count']}")
        for run in intel.get("recent_runs") or []:
            name = run.get("name") or f"playbook {run.get('playbook_id')}"
            status = run.get("status") or "unknown"
            lines.append(f"- {name} — {status}")
    if suggested and label:
        lines.extend(
            [
                "",
                f"**Suggested template:** {label} (`{suggested}`)",
                "Click **Load suggested template** or switch to **Build** to customize.",
                "Need background? Switch to **Explain** for a mini-lesson.",
            ]
        )
    elif rule:
        lines.extend(
            [
                "",
                f"No catalog match for rule `{rule}` — use **Build** + Natural Language, "
                "or add a strict org IR template "
                "(`custom_ir_templates_json`).",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Link a case (ES drilldown, utility playbook, or `container_id` in URL) "
                "for template suggestions.",
            ]
        )

    if ctx.get("es_links") and isinstance(ctx["es_links"], dict):
        mc = ctx["es_links"].get("mission_control")
        if mc:
            lines.append("")
            lines.append("Return to ES Mission Control from the header when done.")

    return {
        "status": "success",
        "coach_lane": "respond",
        "suggested_pattern": suggested,
        "pattern_label": label,
        "case_summary": summary,
        "case_intel": intel,
        "content": "\n".join(lines),
        "investigation_context": {
            k: ctx[k]
            for k in (
                "container",
                "cef",
                "artifact_count",
                "suggested_pattern",
                "wizard_scenario_id",
                "message",
                "event_id",
                "rule_name",
                "investigation_id",
                "es_links",
            )
            if k in ctx
        },
    }
