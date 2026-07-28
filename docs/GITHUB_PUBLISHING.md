# GitHub — wts408/soar-playbook-builder

This repository is the **standalone home** for the SOAR Playbook Builder Splunk SOAR app. It is **not** part of `deslicer/mcp-for-splunk`.

## First-time publish

```bash
cd ~/soar-playbook-builder

git init
git add -A
git status   # confirm: no .env, no scripts/env.e2e.local, no dist/

git commit -m "Initial release: SOAR Playbook Builder 2.26.0"

# Create repo on GitHub (browser or CLI):
#   https://github.com/new → name: soar-playbook-builder → Private or Public

git branch -M main
git remote add origin git@github.com:wts408/soar-playbook-builder.git
git push -u origin main
```

With GitHub CLI:

```bash
gh repo create wts408/soar-playbook-builder --private --source=. --remote=origin --push
```

## Release workflow

```bash
./package_app.sh
git tag v2.26.0
git push origin v2.26.0
```

Action `.github/workflows/release.yml` uploads `dist/soar_playbook_builder.tgz` to the GitHub Release.

## Repository contents

| Path | Purpose |
|------|---------|
| `soar_playbook_builder/` | SOAR app (connector, REST, widgets) |
| `sidecar-ui/` | React builder UI (Build / Run / Coach / Help) |
| `utility_playbooks/` | Open Playbook Builder utility playbook |
| `es_content/` · `soar_content/` | Optional ES ↔ SOAR stitch JSON |
| `docs/` | Install, air-gap, MCP Mode B, on-prem LLM |
| `scripts/` | E2E validation, LLM enablement, packaging helpers |
| `tests/` | Unit tests (no live SOAR required) |

## Mode B (optional NL + LLM)

The SOAR app works standalone (**Mode A** — templates, scaffolds, import, Run tab demos).

For natural-language chat, point asset `mcp_bridge_url` at an MCP agent bridge. Bridge host setup is documented in [MCP_INTEGRATION.md](MCP_INTEGRATION.md) and [ON_PREM_LLM.md](ON_PREM_LLM.md). You may run your own bridge; it does not have to live in this repo.

## Never commit

- SOAR passwords, REST tokens, API keys
- `scripts/env.e2e.local`, `.env`, `.env.secrets`
- Customer Splunk / SOAR license files
