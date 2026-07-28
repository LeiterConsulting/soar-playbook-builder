# On-prem and private LLM deployment

This guide is for customers who run **Mode B** (MCP agent bridge + natural language) with a **fully localized LLM** — no public-cloud model API required. Playbook source and chat text stay inside the customer network when SOAR, the MCP bridge, and the LLM endpoint are all on-prem (or in the same private cloud).

**Related docs:** [ARCHITECTURE.md](./ARCHITECTURE.md) · [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) · [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md)

---

## Summary

| Question | Answer |
|----------|--------|
| Does Playbook Builder require a public-cloud LLM? | **No.** |
| Where is the LLM configured? | On the **MCP bridge host** (`.env` / secrets manager) — **never** on the SOAR app asset. |
| What API does the bridge expect? | **OpenAI-compatible Chat Completions** (`POST /v1/chat/completions`). |
| Do templates, validate, and modern import need an LLM? | **No** — those run on SOAR (Mode A). |
| What needs an LLM? | Open-ended NL **build** and **refine** when no template keyword match exists. |

---

## Trust boundary (on-prem)

```
┌─────────────┐   SOAR session    ┌──────────────────┐   HTTP (internal)   ┌─────────────────┐
│   Analyst   │ ────────────────► │  SOAR Playbook   │ ──────────────────► │  MCP bridge     │
│   browser   │ ◄──────────────── │  Builder app     │ ◄────────────────── │  (customer VM)  │
└─────────────┘                   └──────────────────┘                     └────────┬────────┘
                                                                                     │ HTTP (internal)
                                                                                     ▼
                                                                            ┌─────────────────┐
                                                                            │  On-prem LLM    │
                                                                            │  Ollama / vLLM  │
                                                                            │  LiteLLM / etc. │
                                                                            └─────────────────┘
```

- SOAR asset stores only **`mcp_bridge_url`** (e.g. `http://bridge.internal:8003/agent`).
- **`OPENAI_API_KEY`**, **`OPENAI_BASE_URL`**, and **`AGENT_BRIDGE_MODEL`** live on the bridge host.
- No playbook or chat content is sent to OpenAI.com unless you point `OPENAI_BASE_URL` there.

---

## Capabilities with an on-prem LLM

### Always available (no LLM — Mode A on SOAR)

- Pattern library (ServiceNow, ClearPass, ES notable, enrichment, …)
- **Generate template**, validate, block/code preview
- **Modern visual import** (COA + Python 3.13)
- **Asset preflight** (integration mapping before import)
- Keyword NL (“build a ServiceNow P1 incident…”) via `local_nl_build.py`

### Requires LLM on bridge (Mode B)

- **Novel** natural-language requests that do not match a built-in pattern (e.g. custom WHOIS + tier2 logic)
- **Multi-turn refine** beyond simple rule-based edits (e.g. “add a decision on registrant age”)

### Same on-prem as cloud (when LLM is configured)

- Sidecar **AI connected** (bridge reachable from SOAR)
- MCP SOAR tools (list playbooks, assets, import via IDE) — independent of LLM
- Import path — always runs **on SOAR**, not on the LLM host

**Model quality note:** The bridge system prompt targets SOAR `phantom.app` Python. Smaller local models may need validation/tuning; templates and Mode A remain the fallback.

---

## Requirements for your LLM stack

1. **OpenAI-compatible HTTP API** exposing chat completions (same JSON shape as OpenAI `v1/chat/completions`).
2. **Reachable from the MCP bridge host** (SOAR → bridge → LLM; SOAR does not call the LLM directly).
3. **Model name** known to your server (passed as `AGENT_BRIDGE_MODEL`).
4. Sufficient **context length** for playbook Python (bridge requests up to ~2500 completion tokens).

Common stacks that work:

| Stack | Typical `OPENAI_BASE_URL` |
|-------|---------------------------|
| **Ollama** (OpenAI compatibility) | `http://localhost:11434/v1` |
| **vLLM** | `http://llm.internal:8000/v1` |
| **LiteLLM** gateway | `http://litellm.internal:4000/v1` |
| **Azure OpenAI** (private tenant) | `https://<resource>.openai.azure.com/openai/deployments/<deployment>` — use provider-specific SDK URL format; LiteLLM proxy is often simpler |
| **Text Generation Inference (TGI)** | Use an OpenAI-compatible front proxy or LiteLLM |

---

## Bridge configuration

On the **MCP bridge host**, set environment variables before starting the server (e.g. in `mcp-for-splunk/.env` or a secrets manager):

```bash
# Required for LLM-backed NL build/refine
OPENAI_API_KEY=local-or-gateway-token          # Some servers accept any non-empty string
OPENAI_BASE_URL=http://llm.internal:11434/v1   # Your on-prem OpenAI-compatible endpoint
AGENT_BRIDGE_MODEL=llama3.1:70b                # Must match the model ID your server exposes

# MCP server (defaults shown)
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8003
MCP_STATELESS_HTTP=true
MCP_JSON_RESPONSE=true
```

Start the bridge (from `mcp-for-splunk` repo root):

```bash
cd mcp-for-splunk
uv sync
uv run python src/server.py --transport http --host 0.0.0.0 --port 8003
```

Or use the helper script (stops any existing process on the port first):

```bash
packaging/soar-playbook-builder-app/scripts/enable-llm-playbooks.sh
# Omit OpenAI cloud key — set OPENAI_BASE_URL + AGENT_BRIDGE_MODEL in .env instead
```

### SOAR asset (Playbook Builder)

| Field | Example |
|-------|---------|
| `mcp_bridge_url` | `http://10.0.50.12:8003/agent` |

SOAR must reach this URL from the **SOAR server process** (test with `curl` on the SOAR host, not only from your laptop).

---

## Example: Ollama on the same host as the bridge

```bash
# Terminal 1 — Ollama with a code-capable model
ollama pull llama3.1:70b
ollama serve   # default http://127.0.0.1:11434

# Terminal 2 — MCP bridge
export OPENAI_API_KEY=ollama
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export AGENT_BRIDGE_MODEL=llama3.1:70b
cd mcp-for-splunk
uv run python src/server.py --transport http --host 0.0.0.0 --port 8003
```

Verify:

```bash
curl -sS http://127.0.0.1:8003/agent/health
curl -sS -X POST http://127.0.0.1:8003/agent/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Build a playbook that enriches sender domain via WHOIS and assigns tier2 if registered in the last 30 days","context":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('source' in d, d.get('pattern'))"
```

Expect `"source"` in the JSON response when the LLM path is working.

---

## Example: vLLM behind an internal load balancer

```bash
export OPENAI_API_KEY=not-used
export OPENAI_BASE_URL=https://vllm.internal.company.com/v1
export AGENT_BRIDGE_MODEL=mistral-7b-instruct-v0.3
```

Ensure TLS trust (corporate CA) on the bridge host if using HTTPS.

---

## Example: LiteLLM as a single internal gateway

Point all models through LiteLLM; rotate models without changing SOAR:

```bash
export OPENAI_API_KEY=<litellm-master-key>
export OPENAI_BASE_URL=http://litellm.internal:4000/v1
export AGENT_BRIDGE_MODEL=soar-playbook-builder   # LiteLLM model alias
```

Configure the alias in LiteLLM to route to your preferred on-prem backend.

---

## Air-gapped checklist

- [ ] SOAR app installed; **`mcp_bridge_url`** points to internal bridge only  
- [ ] MCP bridge on a host SOAR can reach (firewall allow-list)  
- [ ] LLM endpoint reachable **only** from bridge (no internet egress required)  
- [ ] `OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL` set on bridge; **no** public OpenAI URL  
- [ ] `curl http://<bridge>:8003/agent/health` succeeds **from SOAR server**  
- [ ] Sidecar shows **AI connected**  
- [ ] Novel NL prompt returns Python `source` (not “Set OPENAI_API_KEY…”)  
- [ ] **`asset_defaults`** configured for ServiceNow / ClearPass / etc. ([CUSTOMIZATION.md](./CUSTOMIZATION.md))  
- [ ] Data-handling review: chat + source flow SOAR → bridge → internal LLM only  

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Sidecar **Templates only** | SOAR cannot reach bridge | Fix `mcp_bridge_url`, network, tunnel |
| **AI connected** but “Set OPENAI_API_KEY…” | Bridge up; LLM not configured or call failed | Set `OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL`; check bridge logs |
| LLM timeout / empty source | Model too small or wrong name | Use larger instruct/code model; verify `AGENT_BRIDGE_MODEL` |
| Import works; NL does not | Mode A still OK; Mode B LLM path broken | Fix bridge LLM env; templates still work |
| Sidecar **AI connected** but “Set OPENAI_API_KEY…” on novel prompts | Bridge up; **LLM call failed** (missing key, placeholder in `.env`, or network/proxy blocks model API) | Load `.env.secrets` and restart MCP; set `NO_PROXY=api.openai.com,openai.com`; or use on-prem `OPENAI_BASE_URL` |
| WHOIS-style **Build** prompt returns refine error | Fixed in latest bridge — old builds treated “adds a note” as refine | Restart MCP after `git pull`; or click **Generate template** for known patterns |

Bridge logs: `mcp-for-splunk/logs/mcp_splunk_server.log`

Implementation reference: `mcp_soar_tutor/agent_bridge/nl_build.py` (`AsyncOpenAI` + `OPENAI_BASE_URL` from environment).

---

## Public cloud vs on-prem (policy comparison)

| | Public OpenAI | On-prem LLM |
|--|---------------|-------------|
| Egress from bridge | Internet | Internal only |
| Keys on SOAR | Never | Never |
| Keys on bridge | `OPENAI_API_KEY` | Gateway token or dummy |
| Template/import path | SOAR-local | SOAR-local |
| NL invent/refine | Yes | Yes (if model sufficient) |

For strict data sovereignty, use **on-prem LLM + internal bridge URL** and leave `OPENAI_BASE_URL` unset or pointed at an internal hostname only.

---

## See also

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Mode A vs Mode B capability matrix  
- [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) — HTTP endpoints and security  
- [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) — SOC engineering handoff  
- Upstream `mcp-for-splunk/env.example` — `OPENAI_BASE_URL`, `AGENT_BRIDGE_MODEL`  
