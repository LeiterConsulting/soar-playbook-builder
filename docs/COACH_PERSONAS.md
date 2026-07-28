# Coach, Assistant & Tutor personas

One SOAR Playbook Builder app — multiple analyst experiences via URL `mode=` or asset **`default_ui_mode`**.

## Personas

| Mode | Audience | Entry URL |
|------|----------|-----------|
| **studio** | Authors (default) | `.../chat` |
| **assistant** | Case-linked build | `.../chat?mode=assistant&container_id=…` |
| **coach** | ES / SOC triage | `.../es_link?...&mode=coach` |
| **tutor** | Training | `.../chat?mode=tutor` |

Coach tabs: `&tab=respond|explain|build` (default **respond**).

## ES Mission Control

```
https://SOAR/rest/handler/DIRECTORY/ASSET/es_link?event_id=$event_id$&rule_name=$rule_name$&mode=coach
```

See `es_content/drilldown_playbook_builder.json`.

## Splunk Enterprise (dashboard / alert)

```
https://SOAR/rest/handler/DIRECTORY/ASSET/splunk_link?rule_name=$name$&src=$src$&mode=coach
```

Optional: `sid`, `dest`, `user`, `container_id` (when case already exists).

## Utility playbook

`open_playbook_builder.py` sets `mode=coach` on **get sidecar url** when `BUILDER_MODE = "coach"`.

## Asset default

Set **`default_ui_mode`** to `coach`, `assistant`, or `tutor` so analysts land in that persona without a query param. URL `mode=` always overrides.

## Lanes

| Tab | Offline? | Purpose |
|-----|----------|---------|
| **Respond** | Yes | Rule → template, case summary, recent playbook runs |
| **Explain** | Yes | Lessons, quizzes, datapath (`tutor_local.py`) |
| **Build** | Templates yes | Scaffold, NL (Mode B), import, run |

Mode B MCP bridge enhances **Build** and NL chat; Respond and Explain work without LLM.
