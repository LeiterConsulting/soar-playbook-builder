# SOAR Playbook Builder

Production Splunk SOAR custom app: describe playbooks, preview block flow and Python source, validate, and import into the Visual Playbook Editor.

**Repository:** [github.com/wts408/soar-playbook-builder](https://github.com/wts408/soar-playbook-builder)  
**Current version:** 2.26.0 · install via `dist/soar_playbook_builder.tgz` (build with `./package_app.sh`)

**Not a demo appliance** — no lab containers, ES datasets, or environment-specific credentials are bundled. Every install **does** include five built-in sample cases (9001–9005), runtime fixtures, and mock-friendly dev mode so you can test Build → Import → Run on your SOAR instance without live notables.

---

## Documentation

| Guide | Contents |
|-------|----------|
| [PLAYBOOK_BUILDER_GUIDE.md](docs/PLAYBOOK_BUILDER_GUIDE.md) | Install, configure, operate, troubleshoot |
| [AIR_GAPPED_OPERATIONS.md](docs/AIR_GAPPED_OPERATIONS.md) | Offline mode — no LLM/MCP |
| [FAILED_LOGINS_QUICK_START.md](docs/FAILED_LOGINS_QUICK_START.md) | Failed Logins → Okta in 15 minutes |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptom index + API |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, Mode A vs Mode B, capabilities matrix |
| [EXAMPLE_WALKTHROUGHS.md](docs/EXAMPLE_WALKTHROUGHS.md) | Reference workflows (generic, no lab data) |
| [NL_TESTING_AND_RECOVERY.md](docs/NL_TESTING_AND_RECOVERY.md) | **NL QA & recovery loop** — test prompts, flowchart, gap handling |
| [RUN_TAB_DEMO.md](docs/RUN_TAB_DEMO.md) | **Run lab demo data** — sample cases 9001–9005, smoke test |
| [WHATS_NEW_PLAIN_ENGLISH.md](docs/WHATS_NEW_PLAIN_ENGLISH.md) | **What's new (2.21–2.22)** — layman's summary of recent updates |
| [AIR_GAP_BUILD_SPEC.md](docs/AIR_GAP_BUILD_SPEC.md) | **Air-gap architecture spec** — capability index, IR, compiler roadmap |
| [DEMO_AND_NL_ENV.md](docs/DEMO_AND_NL_ENV.md) | Demo fixtures, provision API, environment self-healing |
| [ES_SOAR_BUILDER_STITCH.md](docs/ES_SOAR_BUILDER_STITCH.md) | **ES ↔ SOAR ↔ Builder** — drilldowns, utility playbook, case linking |
| [RESPONSE_PLAN_OPEN_BUILDER.md](docs/RESPONSE_PLAN_OPEN_BUILDER.md) | Auto-run Open Playbook Builder when ES export creates cases |
| [CUSTOMIZATION.md](docs/CUSTOMIZATION.md) | Patterns, branding, security |
| [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) | Exact HTTP flow, endpoints, security (Mode B) |
| [ON_PREM_LLM.md](docs/ON_PREM_LLM.md) | **Private / on-prem LLM** — OpenAI-compatible APIs, air-gapped Mode B |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Upstream MCP credit; not a Splunk product |
| [E2E_VALIDATION.md](docs/E2E_VALIDATION.md) | **Pre-GitHub E2E test** — automated run + manual sign-off |
| [REPLICATION_HANDOFF.md](docs/REPLICATION_HANDOFF.md) | SOC engineering checklist |
| [FRESH_INSTALL_AND_MIGRATION.md](docs/FRESH_INSTALL_AND_MIGRATION.md) | **Turnkey install & lab migration** — redeploy to a new SOAR (~15 min) |
| [GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) | **GitHub** — monorepo vs standalone repo, releases, secrets |

---

## Quick start

```bash
git clone https://github.com/wts408/soar-playbook-builder.git
cd soar-playbook-builder
./package_app.sh
# SOAR → Apps → Install App → dist/soar_playbook_builder.tgz
```

1. Create an asset (e.g. `playbook_builder`).  
2. **Mode A (default):** use scaffolds and import — no bridge required.  
3. **Mode B (optional):** set `mcp_bridge_url` to your MCP agent bridge — see [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md).  
4. Open sidecar: `/rest/handler/<directory>/<asset>/chat` (`directory` from `/rest/app`).

```bash
SOAR_URL=https://your-soar:8443 SOAR_USER=admin SOAR_PASS=*** ASSET=playbook_builder \
  ./scripts/print_sidecar_url.sh
```

### Local UI dev (no SOAR required)

```bash
cd sidecar-ui
npm install
npm run dev
# → http://localhost:5173  (mock API: templates, scaffold, NL chat, import, run)
```

For live SOAR from dev: `cp .env.example .env.local`, set `VITE_SOAR_HANDLER_BASE`, restart dev server.

Routes: `#/build` · `#/run` · `#/help` (HashRouter — works inside SOAR sidecar URL).

---

## Deployment modes

| Mode | Bridge | Best for |
|------|--------|----------|
| **A — Localized** | None | Air-gapped, templates, validate, import |
| **B — Bridge + LLM** | MCP host | Open-ended NL chat; LLM on **public cloud or on-prem** — see [ON_PREM_LLM.md](docs/ON_PREM_LLM.md) |

Sidecar URL base: `https://<soar>/rest/handler/<directory>/<asset>/`

---

## Package contents

The installable `.tgz` includes:

- SOAR connector and REST handlers  
- React sidecar (built to static widgets)  
- Local scaffold / validate / import logic  
- **Demo data:** five sample cases (9001–9005), runtime fixtures, and `sample_data/sample_cases.json`

It does **not** include MCP server binaries, ES indexed datasets, or rehearsal scripts.

Optional MCP agent bridge is a **separate** install on a customer-controlled host when using Mode B.

---

## REST routes

| Route | Description |
|-------|-------------|
| `chat` | Sidecar UI + builder API |
| `widget` | VPE poll widget |
| `poll_playbook` | Playbook change fingerprint |
| `proxy_chat` | MCP proxy (advanced) |

---

## Releases

Push a version tag from this repository root:

```bash
./package_app.sh
git tag v2.26.0
git push origin v2.26.0
```

GitHub Actions ([`.github/workflows/release.yml`](.github/workflows/release.yml)) attaches `dist/soar_playbook_builder.tgz` to the Release. See [docs/GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) and [CHANGELOG.md](CHANGELOG.md).

**Before tagging:** run the [validation console](docs/E2E_VALIDATION.md#option-a--validation-console-recommended) or CLI:

```bash
cp scripts/env.e2e.example scripts/env.e2e.local   # edit credentials
./scripts/run-e2e-console.sh
# or: ./scripts/run-e2e-validate.sh auto
```

---

## License

Apache 2.0 (see manifest). Customize `publisher` and branding before internal distribution.
