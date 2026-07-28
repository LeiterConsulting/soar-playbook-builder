# Customization guide

How to adapt the Playbook Builder for your organization without turning it into a bundled demo environment.

---

## Configuration (no code changes)

### Asset settings

| Setting | Purpose |
|---------|---------|
| **mcp_bridge_url** | Base URL for Mode B bridge, e.g. `https://bridge.internal:8003/agent`. Empty = Mode A. |
| **mcp_bridge_allow_insecure_http** | Lab-only plain HTTP bridge override. Default `false`. |
| **soar_loopback_ca_bundle** | Optional PEM CA path for verified SOAR REST loopback. |
| **soar_loopback_allow_insecure_tls** | Lab-only loopback TLS bypass. Default `false`. |
| **ai_instructions** | Short text in the sidecar header (SOC policy, naming standard, change process). |
| **custom_ir_templates_json** | Strict Playbook IR organization templates (`org-*` ids). Review-only until live qualification. |
| **custom_templates_json** | Legacy executable Python templates. Ignored by default. |
| **allow_legacy_python_templates** | Lab-only compatibility switch for legacy Python. Default `false`; enabling it does not make source trusted. |
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

Admins can add org-specific, declarative templates via the Playbook Builder
asset field **`custom_ir_templates_json`**. Valid templates appear in the
sidecar library under **Organization** with **[Org]** and **Strict IR** badges.
They enter the same strict parser, deterministic preflight, and preview compiler
as shipped IR templates. Import remains locked until the live SOAR qualification
gates in [TRUSTED_REVIEW.md](./TRUSTED_REVIEW.md) are complete.

### JSON schema

```json
{
  "schema_version": "1.0",
  "templates": [
    {
      "id": "org-review-note",
      "label": "Organization Review Note",
      "category": "Organization",
      "description": "Format a deterministic analyst review note.",
      "tier": "safe",
      "integrations": [],
      "nl_keywords": ["organization review note"],
      "ir": {
        "schema_version": "1.0.0",
        "id": "org-review-note",
        "name": "Organization Review Note",
        "description": "Format a deterministic analyst review note.",
        "entrypoint": "start",
        "nodes": [
          {"id": "start", "type": "start", "next": "format_note"},
          {
            "id": "format_note",
            "type": "format",
            "template": "Review required",
            "inputs": {},
            "output": "note",
            "next": "complete"
          },
          {"id": "complete", "type": "end", "outcome": "success"}
        ],
        "metadata": {
          "capability_index_version": "organization-template-unbound",
          "operating_mode": "air_gapped",
          "template_id": "org-review-note",
          "labels": ["organization", "review"]
        }
      }
    }
  ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Must start with `org-` (e.g. `org-demo-note`). Cannot override shipped template ids. |
| `ir` | yes | Closed Playbook IR 1.0 object. Both `ir.id` and `metadata.template_id` must exactly match the wrapper `id`. |
| `label` | no | Display name in dropdown |
| `category` | no | Default `Organization` |
| `tier` | no | `safe`, `integration`, or `destructive` (default `integration`) |
| `nl_keywords` | no | Offline NL routing when MCP bridge is unavailable |
| `destructive_actions` | no | Review metadata for destructive tier; this does not authorize execution |
| `integrations` | no | Shown in template description |

The loader accepts at most 128 entries and 1 MiB per configuration field.
Duplicate JSON keys, non-finite values, invalid IR graphs, unknown IR fields,
oversized metadata, and ID drift fail closed. Invalid entries are skipped;
`list_patterns` returns `org_errors` and `org_warnings`, which also appear in
the sidecar chat.

**Copy-paste starter:** `sample_data/sample_org_ir_templates.json` in the
install package (also under `soar_playbook_builder/sample_data/` on SOAR).

### Legacy Python compatibility

`custom_templates_json` contains executable Python and bypasses the declarative
IR/compiler trust boundary. It is ignored unless
`allow_legacy_python_templates=true`. Even when explicitly enabled, the UI marks
these templates **Legacy Python · untrusted**, and they cannot use trusted IR
review. Keep this compatibility switch disabled outside an isolated lab.

### When to use org JSON vs code changes

| Approach | Best for |
|----------|----------|
| **`custom_ir_templates_json`** | Customer-specific declarative starters that need strict offline review without rebuilding the `.tgz` |
| **Legacy `custom_templates_json`** | Isolated compatibility labs only; executable source is untrusted |
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
cd soar-playbook-builder
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
