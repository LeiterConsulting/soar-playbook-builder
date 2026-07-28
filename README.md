# SOAR Playbook Builder

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](soar_playbook_builder/soar_playbook_builder.json)
[![Splunk SOAR 8.5+](https://img.shields.io/badge/SOAR-8.5%2B-65A637)](docs/PLAYBOOK_BUILDER_GUIDE.md)
[![Version](https://img.shields.io/badge/version-2.26.0-informational)](CHANGELOG.md)

**Describe SOAR playbooks in plain language, preview block flow and Python, validate, and import into the Visual Playbook Editor.**

Production Splunk SOAR custom app — not a demo appliance. Every install includes sample cases (9001–9005) and mock-friendly dev mode so you can test **Build → Import → Run** on your own instance.

**Repository:** [github.com/wts408/soar-playbook-builder](https://github.com/wts408/soar-playbook-builder)

---

## At a glance

![Playbook Builder sidecar — chat, template scaffolds, block preview, and Import to SOAR](docs/assets/builder-overview.svg)

*Replace with a live screenshot after install: SOAR → your asset → **Open sidecar** → capture Build tab.*

---

## Prerequisites

### On your build machine (packaging the `.tgz`)

| Requirement | Notes |
|-------------|--------|
| **bash**, **tar**, **git** | macOS or Linux (RHEL/Ubuntu both work) |
| **Node.js 20+** and **npm** | Builds the React sidecar (`sidecar-ui/`) |
| **Python 3.9+** | Utility scripts and optional E2E validation |

Optional (E2E / validation only):

```bash
pip install -r requirements.txt   # httpx for scripts/e2e_validate.py
```

### On Splunk SOAR (runtime)

| Requirement | Notes |
|-------------|--------|
| **Splunk SOAR 8.5+** | See `min_phantom_version` in app manifest |
| **Python 3.13** | SOAR platform Python for imported playbooks |
| **RHEL-compatible OS** | Standard SOAR appliance or self-managed host |
| **Asset + permissions** | Analyst role with playbook edit/import |

**Mode A (default):** templates, scaffolds, validate, import — **no MCP or API keys required.**

**Mode B (optional):** natural-language chat via an external MCP agent bridge — see [Configuration](#configuration) and [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md).

---

## Quick start

Three commands to build the installable app:

```bash
git clone https://github.com/wts408/soar-playbook-builder.git
cd soar-playbook-builder
./package_app.sh
```

Install on SOAR:

1. **SOAR → Apps → Install App** → select `dist/soar_playbook_builder.tgz`
2. **Configure → Asset Configuration** → create an asset (e.g. `playbook_builder`)
3. Run action **Test connectivity** (Mode B) or open the sidecar URL:

```bash
SOAR_URL=https://your-soar:8443 SOAR_USER=admin SOAR_PASS='***' ASSET=playbook_builder \
  ./scripts/print_sidecar_url.sh
```

**Try it without SOAR** (mock UI):

```bash
cd sidecar-ui && npm install && npm run dev
# → http://localhost:5173  (#/build · #/run · #/help)
```

---

## Configuration

Copy the template and fill in values for your environment:

| File | Purpose |
|------|---------|
| [**config.example.yaml**](config.example.yaml) | SOAR asset fields (`mcp_bridge_url`, `asset_defaults`, etc.) |
| [scripts/env.e2e.example](scripts/env.e2e.example) | E2E validation against a live SOAR |
| [sidecar-ui/.env.example](sidecar-ui/.env.example) | Local Vite dev against live SOAR |

**Minimal Mode A asset:** leave `mcp_bridge_url` empty; set `ai_instructions` if desired; map integrations in `asset_defaults` (JSON string in SOAR UI).

**Mode B:** set `mcp_bridge_url` to your bridge (e.g. `http://host:8003/agent`). LLM keys live on the **bridge host**, not in this repo.

Full setup: [docs/PLAYBOOK_BUILDER_GUIDE.md](docs/PLAYBOOK_BUILDER_GUIDE.md)

---

## Deployment modes

| Mode | Bridge | Best for |
|------|--------|----------|
| **A — Localized** | None | Air-gapped, templates, validate, import |
| **B — Bridge + LLM** | MCP host | Open-ended NL chat — [ON_PREM_LLM.md](docs/ON_PREM_LLM.md) |

Sidecar base URL: `https://<soar>/rest/handler/<directory>/<asset>/`

---

## Documentation

| Guide | Contents |
|-------|----------|
| [PLAYBOOK_BUILDER_GUIDE.md](docs/PLAYBOOK_BUILDER_GUIDE.md) | Install, configure, operate, troubleshoot |
| [FAILED_LOGINS_QUICK_START.md](docs/FAILED_LOGINS_QUICK_START.md) | Failed Logins → Okta in ~15 minutes |
| [RUN_TAB_DEMO.md](docs/RUN_TAB_DEMO.md) | Sample cases 9001–9005 smoke test |
| [FRESH_INSTALL_AND_MIGRATION.md](docs/FRESH_INSTALL_AND_MIGRATION.md) | Redeploy to a new SOAR (~15 min) |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Mode A vs B, components |
| [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) | Mode B HTTP flow |
| [AIR_GAPPED_OPERATIONS.md](docs/AIR_GAPPED_OPERATIONS.md) | Offline — no LLM/MCP |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptom index |
| [GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) | Releases and tags |

More guides: [docs/](docs/) · [CHANGELOG.md](CHANGELOG.md)

---

## REST routes

| Route | Description |
|-------|-------------|
| `chat` | Sidecar UI + builder API |
| `widget` | VPE poll widget |
| `poll_playbook` | Playbook change fingerprint |
| `proxy_chat` | MCP proxy (Mode B) |

---

## Releases

```bash
./package_app.sh
git tag v2.26.0
git push origin v2.26.0
```

GitHub Actions attaches `dist/soar_playbook_builder.tgz` to the Release. Pre-tag validation: [docs/E2E_VALIDATION.md](docs/E2E_VALIDATION.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — fork, branch, run tests, open a PR.

---

## License

[MIT License](LICENSE) — customize `publisher` and branding before internal distribution. Not a Splunk product; see [ATTRIBUTION.md](ATTRIBUTION.md).
