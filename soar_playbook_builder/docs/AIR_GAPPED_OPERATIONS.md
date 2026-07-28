# Air-gapped operations

Mode A: templates, guided wizard, and troubleshooting — **no LLM or MCP bridge required**.

## What works offline

| Feature | Usage |
|---------|--------|
| Pattern library | Dropdown → **Use template** → Import |
| Guided wizard | **Excessive Failed Logins** and other scenarios → **Start** |
| Offline NL routing | Keyword match to scaffolds when bridge is down |
| Troubleshooting guide | Search errors → copy fix steps |
| Import / VPE sync | Local `import_draft` on SOAR |

## What requires connectivity (optional Mode B)

| Feature | Requirement |
|---------|-------------|
| Open-ended NL chat | MCP agent bridge reachable from SOAR |
| Sidecar pill **AI connected** | Bridge health + asset test connectivity |

## Recommended asset configuration

| Field | Example |
|-------|---------|
| `mcp_bridge_url` | Leave default or empty in air-gap |
| `ai_instructions` | `Air-gapped — use Guided wizard and Pattern library` |
| `asset_defaults` | `{"okta": "okta", "servicenow": "snow_lab"}` |

## First-time setup checklist

1. Install `soar_playbook_builder.tgz` on SOAR.
2. Create Playbook Builder asset (e.g. `mcpbridge`).
3. Guided wizard → **Excessive Failed Logins → Start**.
4. Import playbook → Open in SOAR (Visual Editor).
5. Configure integration assets (Okta, ServiceNow, etc.) as needed.
6. Test with manual container (see [FAILED_LOGINS_QUICK_START.md](./FAILED_LOGINS_QUICK_START.md)).

## When MCP becomes available

1. Deploy MCP bridge on approved network segment.
2. Set `mcp_bridge_url` on Playbook Builder asset.
3. Run **test connectivity** action.
4. Sidecar pill should show **AI connected** — open-ended NL prompts enabled.

See also:

- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- [FAILED_LOGINS_QUICK_START.md](./FAILED_LOGINS_QUICK_START.md)
- [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)
