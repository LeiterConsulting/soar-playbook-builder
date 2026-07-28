# SOAR Playbook Builder — Replication & Handoff

For **SOC engineering teams** installing and operating the Playbook Builder in a customer Splunk SOAR environment.

Analyst guide: [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md)  
Architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)  
Reference workflows: [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md)

---

## Delivery kit

| Artifact | Purpose | Required |
|----------|---------|----------|
| `soar_playbook_builder.tgz` | SOAR app (sidecar UI, scaffolds, import) | **Yes** |
| Documentation in `docs/` | Install, architecture, customization | **Yes** |
| MCP agent bridge (separate install) | Mode B — NL + LLM | Optional |
| Customer connector apps (Okta, PAN, etc.) | Target integrations | As needed |

The `.tgz` contains **no environment-specific credentials**. It **does** ship built-in demo sample cases (9001–9005), runtime fixtures, and bundled `sample_data/` for optional overrides.

**Migrating to a new SOAR:** [FRESH_INSTALL_AND_MIGRATION.md](./FRESH_INSTALL_AND_MIGRATION.md) — fresh install + asset reconfiguration (~15 min Mode A).

---

## Deployment modes (choose one)

| Mode | MCP bridge | LLM / internet on bridge | Use when |
|------|------------|--------------------------|----------|
| **A — Localized** | Not used | No | Air-gapped, strict egress, templates sufficient |
| **B — Bridge + LLM** | Required | Optional — **on-prem LLM** needs no internet; **cloud LLM** needs egress | Open-ended NL, iterative chat refine |

On-prem / private LLM setup: **[ON_PREM_LLM.md](./ON_PREM_LLM.md)** (OpenAI-compatible API on the bridge host).

Full capability matrix: [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Handoff checklist

### Mode A (minimum)

- [ ] SOAR 8.5.0+
- [ ] Build or obtain `soar_playbook_builder.tgz`
- [ ] Install app; create asset
- [ ] Run **rebuild capability index** and **get sidecar url** on the asset
- [ ] Set `ai_instructions` for your SOC (optional); paste saved `asset_defaults` if migrating
- [ ] Smoke test: Run tab sample **9005** → Create on SOAR → hello template → import → run
- [ ] Document sidecar URL pattern for analysts

### Mode B (additional)

- [ ] Bridge VM/host on network SOAR can reach
- [ ] MCP server + builder bridge plugin installed on bridge host
- [ ] Firewall: SOAR → bridge only (not public 0.0.0.0 without controls)
- [ ] Asset `mcp_bridge_url` set; **Test connectivity** passes from SOAR
- [ ] LLM on bridge host: **cloud** (`OPENAI_API_KEY`) or **on-prem** (`OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL`) — see [ON_PREM_LLM.md](./ON_PREM_LLM.md)
- [ ] Data-handling review complete (traffic stays internal when using on-prem LLM)
- [ ] Fallback documented: analysts can use Mode A if bridge down

---

## Build the SOAR package

```bash
cd packaging/soar-playbook-builder-app
./package_app.sh
# Output: dist/soar_playbook_builder.tgz
```

Verify manifest before customer handoff:

- `publisher`, `description`, `app_version`
- Default `ai_instructions` text (or instruct customer to set on asset)

---

## Validate on a clean SOAR instance

1. Install `.tgz` on non-production SOAR  
2. Create asset; leave bridge URL empty (Mode A smoke test)  
3. Run Walkthrough 1 in [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md)  
4. If Mode B: configure bridge; repeat with chat-based workflow  

---

## Support boundaries

| In scope for customer replication | Out of scope (keep separate) |
|-----------------------------------|------------------------------|
| SOAR app `.tgz` + docs | Presenter-only rehearsal tools |
| Optional MCP bridge install docs | Sample SIEM data / replay kits |
| Pattern customization guide | Lab-specific IPs and tunnels as primary path |
| Connector apps customer already owns | Pre-filled third-party credentials |

---

## Step 8 — E2E validation (before GitHub / production)

Run the automated suite and complete manual sign-off:

```bash
cd packaging/soar-playbook-builder-app
./scripts/run-e2e-validate.sh auto
```

See [E2E_VALIDATION.md](./E2E_VALIDATION.md) for phase-by-phase links and pass criteria.

---

## Version reference

Check `soar_playbook_builder/soar_playbook_builder.json`:

- `app_version` — release label  
- `min_phantom_version` — SOAR compatibility (8.5.0+)  
