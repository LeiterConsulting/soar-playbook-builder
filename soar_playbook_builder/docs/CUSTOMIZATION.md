# Customization guide

How to adapt the Playbook Builder for your organization without turning it into a bundled demo environment.

---

## Configuration (no code changes)

### Asset settings

| Setting | Purpose |
|---------|---------|
| **mcp_bridge_url** | Base URL for Mode B bridge, e.g. `https://bridge.internal:8003/agent`. Empty = Mode A. |
| **ai_instructions** | Short text in the sidecar header (SOC policy, naming standard, change process). |
| **custom_templates_json** | JSON array of org templates (`org-*` ids). See [Organization templates](#organization-templates-no-app-rebuild) below. |
| **asset_defaults** | Map scaffold asset keys to configured SOAR asset names at import. |
| **playbook_defaults_json** | Constants and asset aliases for readiness auto-fix (see Readiness check below). |

### Readiness check (v2.13+)

After NL or template build, the sidecar validates code, integrations, variables, and run context. Configure auto-fill:

```json
{
  "constants": { "SLACK_CHANNEL": "#soc-alerts" },
  "assets": { "slack": "slack_prod" }
}
```

Use **Readiness** → **Apply auto-fixes** in the sidecar. SOAR containers and connector apps cannot be auto-created.

### Publisher and description (manifest)

Before distributing internally or on GitHub, edit `soar_playbook_builder/soar_playbook_builder.json`:

- `publisher` — your team or company name  
- `description` — your supported use cases  
- `license` — your chosen license  

Rebuild with `./package_app.sh` after manifest changes.

---

## Organization templates (no app rebuild)

Admins can add org-specific playbooks via the Playbook Builder asset field **`custom_templates_json`**. Templates appear in the sidecar library under **Organization** with an **[Org]** badge.

### JSON schema

```json
{
  "templates": [
    {
      "id": "org-crowdstrike-isolate",
      "label": "CrowdStrike Host Isolate",
      "category": "Organization",
      "description": "Isolate endpoint via CrowdStrike when severity is high.",
      "tier": "destructive",
      "integrations": ["crowdstrike"],
      "nl_keywords": ["crowdstrike", "isolate host", "contain endpoint"],
      "destructive_actions": ["isolate host"],
      "source": "import phantom.app as phantom\n\ndef on_start(container):\n    phantom.add_note(container=container, content='Isolate host', title='Org')\n    on_finish(container)\n\ndef on_finish(container):\n    phantom.debug('done')\n"
    }
  ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Must start with `org-` (e.g. `org-demo-note`). Cannot override shipped template ids. |
| `source` | yes | Full Python playbook with `on_start(container)`. Validated with `ast.parse` and analyze score. |
| `label` | no | Display name in dropdown |
| `category` | no | Default `Organization` |
| `tier` | no | `safe`, `integration`, or `destructive` (default `integration`) |
| `nl_keywords` | no | Offline NL routing when MCP bridge is unavailable |
| `destructive_actions` | no | Shown in HITL confirm for destructive tier |
| `integrations` | no | Shown in template description |

Invalid entries are skipped; errors return in `list_patterns` → `org_errors` and appear in the sidecar chat on load.

**Copy-paste starter:** `sample_data/sample_org_templates.json` in the install package (also under `soar_playbook_builder/sample_data/` on SOAR).

### When to use org JSON vs code changes

| Approach | Best for |
|----------|----------|
| **`custom_templates_json`** | Customer-specific starters, imported VPE exports, air-gapped sites that cannot rebuild the `.tgz` |
| **Code change** (`builder_helpers.py` + catalog) | Templates you ship to all customers in the community package |

Analysts should not save chat one-offs as templates without admin review — use NL chat for ad hoc builds.

---

## Adding playbook patterns (code path — ship to all users)

Patterns are the primary extension point for customer-specific integrations.

### Server-side scaffold

File: `soar_playbook_builder/builder_helpers.py`

1. Add a pattern key and Python template in the scaffold registry (follow existing `hello`, `clearpass`, etc.).
2. Ensure connector actions `scaffold` and `validate` expose the new key.

### UI label and library entry

Files:

- `sidecar-ui/src/patterns/scenarios.ts` — wizard scenarios (each includes `examplePrompt` for optional **Use in chat**)  
- `sidecar-ui/src/patterns/catalog.ts` — fallback catalog labels  

Keep prompts **generic** (vendor + action), not tied to lab hostnames or sample IPs.

### Offline NL keywords

File: `soar_playbook_builder/local_nl_build.py`

Add keyword → pattern mappings so Mode A users can type natural phrases that resolve to your new scaffold.

### Bridge-side patterns (Mode B only)

If you run the optional MCP agent bridge, align bridge scaffolds with SOAR-side patterns so Mode A and Mode B produce consistent starters.

---

## Branding

| Element | Location |
|---------|----------|
| Colors, spacing | `sidecar-ui/src/App.css` |
| Product title | `sidecar-ui/src/App.tsx` (header) |
| App logo | `soar_playbook_builder/logo.png`, `logo_dark.png` |

After UI changes:

```bash
cd packaging/soar-playbook-builder-app
./package_app.sh
# Reinstall dist/soar_playbook_builder.tgz on SOAR
```

---

## Import behavior

File: `soar_playbook_builder/draft_import.py`

Customize tags, default labels, SCM paths, or timeout behavior. Test import with a non-production SOAR instance first.

---

## Security hardening checklist

- [ ] Do not embed API keys, passwords, or customer IPs in the app package  
- [ ] Use Mode A in air-gapped SOAR; disable or omit `mcp_bridge_url`  
- [ ] Mode B: TLS terminate at bridge; restrict SOAR → bridge with firewall  
- [ ] Mode B: store LLM config on bridge only — `OPENAI_API_KEY`, **`OPENAI_BASE_URL`**, **`AGENT_BRIDGE_MODEL`** (see [ON_PREM_LLM.md](./ON_PREM_LLM.md) for on-prem)  
- [ ] Set `ai_instructions` to document your data-handling policy for analysts  
- [ ] Restrict SOAR roles that can install custom apps and run import  
- [ ] Review LLM data path: on-prem endpoint = no external egress; cloud = provider terms apply  

---

## What not to ship in the production `.tgz`

| Exclude | Reason |
|---------|--------|
| Sample notables / replay scripts | Environment-specific |
| Demo presenter apps | Not part of SOAR app |
| Lab Docker compose | Customer infra differs |
| Hardcoded SOAR URLs or UUIDs in Python/JS | Breaks OOTB install |
| Pre-configured Okta/ServiceNow credentials | Security |

The build script packages only `soar_playbook_builder/` — keep ancillary material in separate repos or `docs/` only.

---

## Version and rebuild workflow

1. Bump `app_version` in `soar_playbook_builder.json`  
2. `./package_app.sh`  
3. Test on a clean SOAR 8.5+ instance  
4. Publish `dist/soar_playbook_builder.tgz` + changelog  

See [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) for validation checklist.
