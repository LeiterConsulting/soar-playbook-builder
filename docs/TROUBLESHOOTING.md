# Troubleshooting guide

Symptom index for Playbook Builder on SOAR. The sidecar **Troubleshooting guide** searches this catalog at runtime (no internet).

## Quick index

| Symptom | Entry ID |
|---------|----------|
| Templates only / AI offline | `templates_only` |
| MCP bridge unreachable | `mcp_bridge_unreachable` |
| Build timeout / HTTP 500 | `build_timeout` |
| Import blocked — integrations | `needs_assets` |
| Okta missing | `okta_asset_missing` |
| Invalid datapath in VPE | `vpe_invalid_datapath` |
| soar Missing Configuration | `vpe_soar_missing_config` |
| Import failed | `import_failed` |
| Okta get user failed at runtime | `okta_get_user_failed` |
| ES / Mission Control no SOAR export | `es_soar_export_missing` |
| Sidecar 404 / blank | `sidecar_blank_404` |
| No draft to import | `no_draft` |

## API (for integrators)

```
GET /rest/handler/<directory>/<asset>/chat?action=troubleshoot&q=okta
```

Returns `{ "status": "success", "entries": [...], "count": N }`.

Error responses from build/import include `troubleshooting` when a match is found.

For **NL testing**, unsupported integrations, and the operator recovery loop (flowchart + test prompts), see [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md).

## Detailed entries

See `soar_playbook_builder/troubleshooting_catalog.py` — the single source of truth bundled with the app.

## When to escalate

1. Reproduce with **Hello World** template — if that fails, app install or SOAR permissions issue.
2. If Hello works but Okta fails — asset/token/artifact fields (see `okta_get_user_failed`).
3. If VPE broken after import — delete playbook, upgrade app, re-import (see `vpe_invalid_datapath`).
