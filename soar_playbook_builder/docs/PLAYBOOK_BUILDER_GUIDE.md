# SOAR Playbook Builder — User & Setup Guide

A plain-language guide for installing, configuring, and using the Playbook Builder in your Splunk SOAR environment.

**Current version:** 2.7.2  
**App package:** `soar_playbook_builder.tgz`

**Also read:** [ARCHITECTURE.md](./ARCHITECTURE.md) (Mode A vs B) · [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) · **[ON_PREM_LLM.md](./ON_PREM_LLM.md)** (private/on-prem LLM) · [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md) · **[NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md)** (NL QA & recovery loop) · [CUSTOMIZATION.md](./CUSTOMIZATION.md) · [ATTRIBUTION.md](../ATTRIBUTION.md)

---

## What is this?

The **SOAR Playbook Builder** is a sidecar web UI that runs inside Splunk SOAR. It helps analysts:

- Describe playbooks in **plain language** (with optional AI assistance)
- Preview workflows as **blocks, diagrams, and storyboards**
- Generate **starter templates** (ClearPass, ES notables, indicator enrichment, and more)
- **Validate** Python playbook code
- **Import** drafts directly into SOAR and open them in the Visual Playbook Editor (VPE)

You can use it in two modes:

| Mode | What you get | MCP required? |
|------|--------------|---------------|
| **Mode A — Localized / templates** | Scaffold patterns, preview, validate, import | No |
| **Mode B — Bridge + LLM** | Open-ended NL chat and refine | Yes (bridge; LLM can be **cloud or on-prem** — see [ON_PREM_LLM.md](./ON_PREM_LLM.md)) |

---

## How the pieces fit together

Think of it as three layers. Only the SOAR app is required; MCP is optional but unlocks AI chat.

```
┌──────────────────────────────────────────────────────────────────────┐
│  YOUR BROWSER                                                        │
│                                                                      │
│   ┌─────────────────────┐      ┌─────────────────────────────────┐ │
│   │  SOAR Playbooks     │      │  Playbook Builder sidecar       │ │
│   │  (Visual Editor)    │ ◄────│  Chat · Preview · Import        │ │
│   └─────────────────────┘      └───────────────┬─────────────────┘ │
└────────────────────────────────────────────────┼────────────────────┘
                                                 │
                                    Same SOAR server (REST API)
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  SPLUNK SOAR SERVER                                                  │
│                                                                      │
│   SOAR Playbook Builder app (soar_playbook_builder)               │
│   • Serves the sidecar UI                                            │
│   • Runs scaffolds, validate, import locally                         │
│   • Optionally forwards chat to MCP bridge                           │
└────────────────────────────────────────────┬─────────────────────────┘
                                             │
                         Optional: MCP bridge URL (HTTP)
                                             │
                                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MCP SERVER (analyst workstation or shared host)                     │
│                                                                      │
│   MCP agent bridge (optional, customer host)                           │
│   • Natural-language playbook building                               │
│   • LLM responses (when API key configured on bridge)                │
│   • Optional IDE integration via same MCP server                     │
└──────────────────────────────────────────────────────────────────────┘
```

### Component summary

| Component | What it is | Where it runs |
|-----------|------------|---------------|
| **SOAR app** | Installed Splunk SOAR app with connector + UI | SOAR server |
| **Sidecar UI** | React web app (chat + preview panels) | Served by SOAR app |
| **Connector** | Python REST handler (`playbook_builder_connector.py`) | SOAR server |
| **MCP agent bridge** | Optional NL/LLM backend | Customer-controlled host |
| **SSH tunnel** | Dev-only convenience when bridge is not on SOAR network | Not recommended for production |

---

## What you receive (packaging & delivery)

**SOC engineering handoff:** see [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) for step-by-step replication, validation checklist, and deployment modes.

Customers typically receive a **kit** with one or more of these:

### 1. SOAR app (required) — `soar_playbook_builder.tgz`

This is the main deliverable. Install it through the SOAR Apps UI.

**Built by:**
```bash
cd packaging/soar-playbook-builder-app
./package_app.sh
# Output: dist/soar_playbook_builder.tgz
```

The build script:
1. Compiles the React sidecar into static JS/CSS
2. Bundles the SOAR app folder into a `.tgz` tarball
3. Verifies the package is clean (no macOS junk files)

**Distribution channels:**
- Direct file handoff (PS engagement, secure download)
- Splunkbase (SOAR app listing — when published)
- Internal artifact repository

### 2. MCP server (optional) — for AI chat & Cursor

Separate from the SOAR app. Distributed via:

- **Source:** Community MCP server distribution (e.g. [mcp-for-splunk](https://github.com/deslicer/mcp-for-splunk)) with Playbook Builder bridge support
- Install bridge plugin per bridge host documentation

Used when you want:
- Natural-language playbook building in the sidecar
- Playbook tools inside Cursor IDE
- Shared AI backend for a team

### 3. Documentation & examples

- This guide
- Pattern/scaffold examples for customer-specific integrations
- Optional Cursor MCP configuration snippet

---

## Prerequisites

### SOAR app only (minimum)

- Splunk SOAR **8.5.0+**
- Permission to install apps (Apps → Install App)
- Permission to create/configure an app **asset**
- Modern browser (Chrome, Firefox, Edge)

### Full NL + AI mode (optional)

- MCP server host (Linux or macOS) with Python 3.10+
- Network path from **SOAR server → MCP bridge URL**
  - Common pattern: SSH reverse tunnel when MCP runs on an analyst laptop
  - Production pattern: MCP on a VM SOAR can reach directly (no tunnel)
- Optional: `OPENAI_API_KEY` (or compatible LLM endpoint) for AI responses

---

## Installation

### Step 1 — Install the SOAR app

1. Obtain `soar_playbook_builder.tgz`
2. In SOAR: **Apps → Install App**
3. Upload the `.tgz` file
4. Confirm the app appears as **SOAR Playbook Builder**

### Step 2 — Create an asset

1. Go to **Apps → SOAR Playbook Builder**
2. Click **Create Asset** (or configure an existing one)
3. Name it something memorable, e.g. `mcpbridge` or `playbook_builder`
4. Save the asset

### Step 3 — Configure the asset

| Setting | Required? | Example | Purpose |
|---------|-----------|---------|---------|
| **mcp_bridge_url** | No (for offline mode) | `http://127.0.0.1:8003/agent` | Where SOAR sends chat for NL/AI |
| **ai_instructions** | No | `Production SOAR — classic Python playbooks` | Short label shown in the sidecar header |

**Offline-only setup:** Leave `mcp_bridge_url` at default or blank. Scaffolds and import still work.

**Full AI setup:** Set `mcp_bridge_url` to a URL SOAR can reach (see [MCP setup](#optional-mcp-server-setup) below).

### Step 4 — Test connectivity

1. On the asset, run the **Test connectivity** action
2. Expected: success message with sidecar URL hint
3. If MCP is configured, this also checks whether the bridge is reachable from SOAR

### Step 5 — Open the sidecar

The sidecar URL follows this pattern:

```
https://<your-soar-host>/rest/handler/<directory>/<asset-name>/chat
```

**Important:** Use the **`directory`** field from SOAR's app registry — not the package name.

Example:
```
https://your-soar.example.com:8443/rest/handler/soarplaybookbuilder_<uuid>/playbook_builder/chat
```

**Easy way to get the URL** (after install):

```bash
cd packaging/soar-playbook-builder-app
SOAR_URL=https://your-soar:8443 \
SOAR_USER=your_user \
SOAR_PASS=your_password \
ASSET=mcpbridge \
./scripts/print_sidecar_url.sh
```

Bookmark this URL. Pin it in your browser or add it to SOAR navigation if your org supports custom links.

---

## Optional: MCP server setup

Skip this section if you only need templates and manual editing.  
**Detailed HTTP contract:** [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)

### Option A — MCP on same network as SOAR (recommended for production)

1. Install MCP on a server SOAR can reach:

```bash
git clone <mcp-for-splunk-repo>
cd mcp-for-splunk
uv sync
uv run mcp-server --local --detached
```

2. Verify locally:

```bash
curl http://127.0.0.1:8003/agent/health
# Expect JSON with status ok
```

3. Set asset **mcp_bridge_url** to:
   ```
   http://<mcp-host-ip>:8003/agent
   ```

4. From the **SOAR server**, verify:

```bash
curl http://<mcp-host-ip>:8003/agent/health
```

### Option B — Bridge on a reachable host (production)

See [ARCHITECTURE.md](./ARCHITECTURE.md) for network and security guidance. Prefer a dedicated bridge VM with firewall allow-list from SOAR — not a public-facing port without TLS and auth.

### Option C — Development tunnel (non-production only)

Some teams temporarily use an SSH reverse tunnel while testing. Do not document this as the customer handoff pattern. Use Option A or B for production.

### Optional: LLM for smarter responses

The bridge supports **public-cloud** and **on-prem** models via an OpenAI-compatible Chat Completions API. Full guide: **[ON_PREM_LLM.md](./ON_PREM_LLM.md)**.

**Public cloud (OpenAI):**

```bash
export OPENAI_API_KEY=sk-...
export AGENT_BRIDGE_MODEL=gpt-4o-mini
uv run python src/server.py --transport http --host 0.0.0.0 --port 8003
```

**On-prem (example — Ollama on the bridge host):**

```bash
export OPENAI_API_KEY=ollama
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export AGENT_BRIDGE_MODEL=llama3.1:70b
uv run python src/server.py --transport http --host 0.0.0.0 --port 8003
```

Without a reachable LLM endpoint, the bridge falls back to rule-based pattern matching (still useful for known templates like ServiceNow P1 or Palo Alto block IP). Open-ended prompts (e.g. custom WHOIS logic) require a configured LLM.

### Optional: Cursor IDE integration

For power users who build playbooks in Cursor:

```json
{
  "mcpServers": {
    "splunk": {
      "url": "http://localhost:8003/mcp/",
      "headers": {
        "X-MCP-Toolsets": "splunk,soar,<builder-bridge-toolset>",
        "X-SOAR-URL": "https://your-soar:8443",
        "X-SOAR-USER": "your_user",
        "X-SOAR-PASSWORD": "your_password",
        "X-SOAR-SSL-VERIFY": "false"
      }
    }
  }
}
```

Restart Cursor after changing MCP config.

---

## How to use the sidecar

### Layout

| Left panel | Right panel |
|------------|-------------|
| Guided **steps** and example **prompts** | **Workflow preview** (Blocks / Diagram / Story / Code) |
| **Chat** for NL requests | **Import to SOAR**, **Open in SOAR**, **All Playbooks** |
| | **Generate template**, **Validate**, **Poll VPE** |

### Typical workflow

1. **Describe** what you want in chat, or pick a pattern from the dropdown (e.g. ClearPass Quarantine)
2. **Preview** updates in the right panel — review Blocks and Code tabs
3. **Validate** to check Python structure and common mistakes
4. **Import to SOAR** — packages the Code tab source and imports into SOAR
5. Wait for **✓ Synced: &lt;playbook name&gt; (id …)** confirmation
6. Click **Open in SOAR** — opens *your* imported playbook in the Visual Editor

### Important behavior: linked playbook vs URL parameter

If your sidecar URL contains `?playbook_id=123`:

- That ID is **ignored** for "Open in SOAR" until you import/sync
- This prevents accidentally opening an old/unrelated playbook (e.g. an Office 365 template)
- After import, the sidecar tracks the **correct** playbook ID automatically

### Built-in patterns (offline scaffolds)

| Pattern | Use case |
|---------|----------|
| Hello World | Minimal starter playbook |
| Aruba ClearPass Quarantine | NAC quarantine when risk score is high |
| ES Notable Response | Triage and respond to Splunk ES notables |
| Indicator Enrichment | Enrich IOCs before taking action |

Natural-language requests like *"Build a Palo Alto block IP playbook"* also work via pattern matching, even without MCP.

---

## REST API routes (reference)

Base: `https://<soar>/rest/handler/<directory>/<asset>/`

| Route | Method | Purpose |
|-------|--------|---------|
| `chat` | GET | Sidecar UI page |
| `chat?action=steps` | GET | Builder step definitions |
| `chat?action=scaffold&pattern=…` | GET | Generate template |
| `chat?action=validate&pattern=…` | GET | Validate current pattern/source |
| `chat?message=…` | GET | Send chat message (NL build) |
| `chat?action=bridge_status` | GET | Check MCP reachability from SOAR |
| `chat?poll=1&playbook_id=…` | GET | Poll for VPE changes |
| `chat` | POST | Import draft (`action=import_draft`) |
| `widget` | GET | Compact VPE poll widget |
| `poll_playbook` | GET/POST | Playbook change fingerprint |

---

## Troubleshooting

### Sidecar page is blank or 404

| Check | Action |
|-------|--------|
| Wrong URL path | Use `directory` from `/rest/app`, not package name `soar_playbook_builder` |
| App not installed | Reinstall `soar_playbook_builder.tgz` |
| Asset name wrong | URL must use your asset name, e.g. `/mcpbridge/chat` |
| App disabled | Enable app in SOAR Apps UI |

Run `./scripts/print_sidecar_url.sh` to print the correct URL.

### "MCP bridge not reachable" / offline mode

This means **SOAR cannot reach** the MCP bridge URL — not necessarily that your laptop tunnel is down.

| Check | Where | Command / action |
|-------|-------|------------------|
| MCP running | MCP host | `curl http://127.0.0.1:8003/agent/health` |
| Tunnel up | SOAR server | `curl http://127.0.0.1:8003/agent/health` |
| Asset URL correct | SOAR asset | Should match where SOAR can reach MCP |
| Firewall | Network | Allow SOAR → MCP on port 8003 |

**Workaround:** Use **Generate template** and pattern dropdown — these work without MCP.

### Import to SOAR fails or no confirmation

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No feedback | Old app version | Upgrade to 2.4.0+ |
| "Build first" message | No source in Code tab | Generate template or send NL message first |
| Sync error in red | SOAR REST/SCM issue | Check SOAR logs; verify playbook import permissions |
| Timeout after 60s | SOAR under load | Retry; check connector logs |

Always wait for **✓ Synced** before clicking **Open in SOAR**.

### Open in SOAR shows the wrong playbook

| Cause | Fix |
|-------|-----|
| Opened before import | Click **Import to SOAR** first; wait for sync confirmation |
| Stale `?playbook_id=` in URL | Ignore it — sidecar uses linked ID after import only |
| Old app version | Upgrade to 2.4.0+ |

### Chat times out

- Default timeout: ~25 seconds for GET, ~60 seconds for import POST
- Usually indicates MCP unreachable or LLM slow
- Try **Generate template** to confirm SOAR app itself is working

### Test connectivity action fails

1. Verify asset exists and app is enabled
2. If MCP configured: verify health URL from SOAR server
3. Check SOAR connector logs for Python errors

### React UI looks unstyled

- Ensure `playbook_builder.css` and `playbook_builder.js` exist in the app widgets folder
- Reinstall from a fresh `package_app.sh` build (v2.6.0+)
- Hard-refresh browser (Ctrl+Shift+R)

---

## Customizing for your environment

See [CUSTOMIZATION.md](./CUSTOMIZATION.md) for patterns, branding, and security checklist.

| What to customize | Where |
|-------------------|-------|
| New playbook patterns / scaffolds | `builder_helpers.py` + `sidecar-ui/src/patterns/registry.ts` |
| Header context text | Asset setting `ai_instructions` |
| NL pattern matching (Mode A) | `local_nl_build.py` |
| Import behavior | `draft_import.py` |
| Branding / colors | `sidecar-ui/src/App.css` → rebuild with `package_app.sh` |

---

## Security notes

- **Credentials:** SOAR asset stores `mcp_bridge_url` only — not SOAR passwords. MCP/Cursor config holds SOAR credentials separately.
- **Network:** Prefer private network or SSH tunnel for MCP bridge. Do not expose port 8003 to the public internet without authentication.
- **LLM:** If using `OPENAI_API_KEY`, playbook source may be sent to the LLM provider — review your data handling policy.
- **SOAR permissions:** Import requires a SOAR user/account with playbook create/import rights.

---

## Quick reference checklist

### Minimum setup (no MCP)

- [ ] Install `soar_playbook_builder.tgz`
- [ ] Create asset
- [ ] Open sidecar URL
- [ ] Generate template → Validate → Import → Open in SOAR

### Full setup (with AI chat)

- [ ] All of the above, plus:
- [ ] MCP server running (`uv run mcp-server --local --detached`)
- [ ] Network path SOAR → MCP (direct or SSH tunnel)
- [ ] Asset `mcp_bridge_url` configured
- [ ] `curl …/agent/health` succeeds **from SOAR server**
- [ ] Test connectivity action passes
- [ ] Optional: `OPENAI_API_KEY` set on MCP host

---

## Support & version info

| Item | Value |
|------|-------|
| App name | SOAR Playbook Builder |
| Package name | `soar_playbook_builder` |
| App ID | `a7c3e891-4f2d-4b18-9e6a-1d5f8c2b0e47` |
| Min SOAR version | 8.5.0 |
| Sidecar UI | React — builds to `playbook_builder.js` |

**Reference workflows:** [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md)  
**Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## FAQ

**Do I need MCP for basic use?**  
No. Scaffolds, preview, validate, and import work offline on the SOAR server.

**Do I need Cursor?**  
No. Cursor is optional for power users who want MCP tools in their IDE.

**Can this run on Splunk Enterprise instead of SOAR?**  
Not today. This package is a SOAR app. An ES dashboard version is a possible future add-on using the same React UI core.

**How do I get updates?**  
Install a newer `soar_playbook_builder.tgz` through Apps → Install App (upgrade/replace per your SOAR admin process).

**Where is the playbook stored before import?**  
In the sidecar's Code tab (in browser memory). Click **Import to SOAR** to push it into SOAR's playbook repository.

**What format does SOAR import use?**  
Classic Python playbook packaged as `.tgz`, imported via SOAR REST `/rest/import_playbook`.
