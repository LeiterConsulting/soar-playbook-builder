# SOAR Playbook Builder — Architecture

This document describes how the Playbook Builder is structured, where each component runs, and how the two supported deployment modes differ.

---

## Design principle: SOAR-native UI, optional external bridge

The Playbook Builder is a **Splunk SOAR custom application**. All analyst-facing UI and SOAR integration (REST handlers, import, VPE links) run **on the SOAR platform**. An optional **MCP agent bridge** on a separate host adds natural-language and LLM capabilities when your security policy allows outbound access from that host.

Nothing in the SOAR app ships sample data, lab containers, or environment-specific credentials. Customers install the `.tgz`, configure one asset, and use their own SOAR instance, connectors, and playbooks.

---

## Component map

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Analyst browser                                                        │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐ │
│  │ SOAR UI (Playbooks/VPE)  │  │ Playbook Builder sidecar (SOAR app)  │ │
│  │  Open Visual Editor ◄────┼──┼── same-origin deep links             │ │
│  └──────────────────────────┘  └───────────────┬──────────────────────┘ │
└────────────────────────────────────────────────┼────────────────────────┘
                                                 │ HTTPS (SOAR session)
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Splunk SOAR server                                                     │
│                                                                         │
│  soar_playbook_builder (information service app)                     │
│  • playbook_builder_connector.py — REST routes                          │
│  • builder_helpers.py — scaffolds, validate, preview (local)            │
│  • draft_import.py — package + import_playbook                          │
│  • local_nl_build.py — offline NL pattern matching                      │
│  • capability/ — local SOAR introspection index (air-gap step 1)       │
│  • Sidecar UI (React → static JS/CSS in widgets/)                       │
│  • Optional: proxy chat → MCP bridge URL (asset setting)                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
              Optional HTTP  │  (only when mcp_bridge_url is set)
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP agent bridge host (customer-controlled VM / tooling subnet)          │
│                                                                         │
│  Community MCP server (e.g. mcp-for-splunk) + builder bridge plugin     │
│  • POST /agent/api/chat — NL refine, LLM when API key configured        │
│  • POST /agent/api/draft — draft cache for multi-turn build             │
│  • GET  /agent/health — reachability check from SOAR                    │
│                                                                         │
│  Credentials (SOAR REST, Splunk, LLM API keys) stay on this host.      │
└─────────────────────────────────────────────────────────────────────────┘
```

| Component | Runs on | Required? |
|-----------|---------|-----------|
| SOAR app (`soar_playbook_builder.tgz`) | SOAR | **Yes** |
| Sidecar UI + local scaffolds | SOAR (served by app) | **Yes** (bundled) |
| MCP agent bridge | Customer network | **No** (Mode B only) |
| LLM provider API | Via bridge host egress | **No** (optional within Mode B) |
| Splunk ES / sample data | Customer environment | **No** (your integrations only) |

---

## Deployment modes

### Mode A — Localized (templates-only)

**All playbook building logic that does not require an external model runs inside SOAR.**

| Capability | Available |
|------------|-----------|
| Pattern library (Hello World, ClearPass, ES notable, enrichment, etc.) | Yes |
| Generate template / scaffold | Yes |
| Block, diagram, storyboard, and code preview | Yes |
| Validate Python structure | Yes |
| Import draft → SOAR playbook repository | Yes |
| Open imported playbook in Visual Editor | Yes |
| VPE poll / sync status | Yes |
| Rule-based NL pattern matching (`local_nl_build.py`) | Yes |
| LLM-authored or open-ended NL chat | **No** |
| Multi-turn refine via external draft cache | **No** |
| Cursor / IDE agent tools | **No** |

**Network:** SOAR only. No outbound dependency on a bridge host. Suitable for air-gapped, restricted, or high-assurance environments.

**Asset config:** Leave `mcp_bridge_url` unset or at default. Sidecar shows **Templates only** when bridge is unreachable.

---

### Mode B — Bridge + LLM (natural language + AI)

**SOAR app unchanged; chat and advanced NL are proxied to an MCP agent bridge.**

| Capability | Available |
|------------|-----------|
| Everything in Mode A | Yes |
| Open-ended natural language requests | Yes |
| LLM-generated scaffolds and refinements (when API key set on bridge) | Yes |
| Shared draft cache across chat turns | Yes |
| Optional: Splunk/SOAR tools on bridge for IDE users | Yes (MCP host) |

**Network:** SOAR server must reach `mcp_bridge_url` (HTTPS or HTTP per policy). The bridge host calls the LLM:

- **Public cloud** — OpenAI, Azure OpenAI, etc. (internet egress from bridge)
- **On-prem / private** — Ollama, vLLM, LiteLLM, or any **OpenAI-compatible** endpoint on the customer network (**no internet egress required**)

See **[ON_PREM_LLM.md](./ON_PREM_LLM.md)** for localized LLM configuration (`OPENAI_BASE_URL`, `AGENT_BRIDGE_MODEL`, air-gapped checklist).

**Security posture:**

- SOAR asset stores **only the bridge URL**, not LLM keys.
- LLM and Splunk/SOAR service credentials live on the **bridge host** under customer control.
- Review data-handling policy: playbook source and chat text are sent to the **LLM endpoint configured on the bridge** when Mode B NL generation runs. With an on-prem LLM, that traffic stays inside the customer network.

**Production pattern:** Dedicated bridge VM on a network segment SOAR can reach (firewall allow-list). Avoid exposing port 8003 to the public internet without authentication and TLS termination.

---

## Mode comparison (what one can do that the other cannot)

| Task | Mode A (localized) | Mode B (bridge + LLM) |
|------|--------------------|------------------------|
| Install and use with zero external services | Yes | No (needs bridge) |
| Air-gapped SOAR | Yes | No |
| Pick a named pattern and import | Yes | Yes |
| “Build a playbook that …” free-form prose | Limited (keyword patterns) | Full NL + LLM |
| Iterative chat refine (“add a decision on severity”) | Limited | Yes |
| Customize patterns in `builder_helpers.py` only | Yes | Yes |
| Use Cursor MCP for same build tools | No | Yes (optional) |
| Control where LLM traffic exits | N/A (no LLM) | Yes (bridge host egress) |

---

## Sidecar UI architecture

The sidecar is a React app built to static assets (`playbook_builder.js`, `playbook_builder.css`) and served by the SOAR REST handler at `/chat`.

| Panel | Responsibility |
|-------|----------------|
| Left — steps & prompts | Guided flow; example prompts (generic integration scenarios) |
| Left — chat | NL messages → connector → local build or MCP proxy |
| Right — preview | Blocks, diagram (Mermaid), storyboard, Python source |
| Right — actions | Validate, Import, Open in SOAR, Poll VPE |

Preview enrichment is produced server-side by `preview_visual.py` on scaffold and NL responses.

---

## REST handler routes

Base: `https://<soar>/rest/handler/<directory>/<asset>/`

| Route | Purpose |
|-------|---------|
| `chat` | Sidecar page + JSON API (scaffold, validate, chat, import) |
| `widget` | Compact VPE poll widget |
| `poll_playbook` | Playbook change fingerprint for live sync |
| `proxy_chat` | Direct MCP proxy (advanced) |

The `directory` value comes from SOAR’s app registry (`/rest/app`), derived from the display name **SOAR Playbook Builder**, not from `package_name`.

---

## Data flows

### Scaffold (both modes)

1. User selects pattern or sends NL text  
2. Connector runs `scaffold_pattern()` locally **or** proxies to MCP  
3. `attach_visual_preview()` adds blocks, Mermaid, storyboard  
4. Browser renders preview; source held in session until Import  

### Import (both modes)

1. User clicks **Import to SOAR**  
2. `draft_import.py` packages Python → `.tgz`  
3. SOAR REST `import_playbook`  
4. Connector resolves playbook ID; sidecar links **Open in Visual Editor**  

### Chat proxy (Mode B only)

1. Sidecar POST/GET chat with message  
2. Connector forwards to `{mcp_bridge_url}/api/chat`  
3. Bridge returns enriched payload; connector adds SOAR deep links  

---

## Extensibility (customer-owned)

| Extension | Location |
|-----------|----------|
| New scaffolds / patterns | `builder_helpers.py`, `sidecar-ui/src/patterns/registry.ts` |
| Header / SOC context string | Asset `ai_instructions` |
| Offline NL keywords | `local_nl_build.py` |
| Bridge-side NL / LLM patterns | MCP bridge plugin (separate install) |
| Branding | `sidecar-ui/src/App.css` → rebuild `.tgz` |

See [CUSTOMIZATION.md](./CUSTOMIZATION.md) for step-by-step instructions.

---

## Related documentation

| Document | Audience |
|----------|----------|
| [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md) | Install, configure, operate |
| [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) | SOC engineering handoff checklist |
| [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) | Exact MCP HTTP contract and sequences |
| [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md) | Reference workflows (not environment-specific) |
| [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md) | NL QA, recovery flowchart, gap handling |
| [CUSTOMIZATION.md](./CUSTOMIZATION.md) | Patterns, branding, bridge setup |
