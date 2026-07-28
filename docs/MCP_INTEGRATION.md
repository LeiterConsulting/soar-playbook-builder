# MCP integration — how it works

This document explains **exactly** how the SOAR Playbook Builder connects to an optional MCP agent bridge (Mode B). For when to use Mode A vs B, see [ARCHITECTURE.md](./ARCHITECTURE.md).

**Attribution:** The bridge is not a Splunk product. See [ATTRIBUTION.md](../ATTRIBUTION.md).

---

## Summary

| Question | Answer |
|----------|--------|
| Is MCP required? | **No.** Mode A works without it. |
| Who calls whom? | **SOAR app → MCP bridge** (server-side HTTP from the connector). The browser never talks to MCP directly. |
| What is stored in SOAR? | Asset field `mcp_bridge_url` only (e.g. `https://bridge.internal:8003/agent`). No LLM API keys in the SOAR app. |
| What runs on the bridge? | Community MCP server + builder agent routes (`/agent/api/*`). |
| What if bridge is down? | Scaffolds, validate, import still work (Mode A). Chat falls back to local keyword NL when possible. |

---

## Actors and trust boundaries

```
┌──────────────┐     HTTPS (SOAR session)      ┌─────────────────────────────┐
│   Browser    │ ────────────────────────────► │  SOAR Playbook Builder app │
│  (analyst)   │ ◄──────────────────────────── │  playbook_builder_connector│
└──────────────┘     same-origin /chat JSON    └──────────────┬──────────────┘
                                                               │
                                    HTTP POST/GET (no browser) │
                                    from SOAR Python process │
                                                               ▼
                                                ┌─────────────────────────────┐
                                                │  MCP agent bridge host       │
                                                │  GET  /agent/health          │
                                                │  POST /agent/api/chat        │
                                                │  POST /agent/api/draft       │
                                                └──────────────┬──────────────┘
                                                               │ optional
                                                               ▼
                                                ┌─────────────────────────────┐
                                                │  LLM provider (egress)       │
                                                │  only if API key on bridge   │
                                                └─────────────────────────────┘
```

**Trust implications**

- Analyst auth is SOAR’s normal web session (cookie) for the sidecar only.
- MCP bridge must be reachable **from the SOAR server process**, not from the analyst laptop (unless SOAR and laptop are the same host in dev).
- Protect bridge URL with network policy; do not expose `:8003` on the public internet without TLS and access controls.

---

## Configuration

### SOAR asset (`soar_playbook_builder`)

| Field | Example | Purpose |
|-------|---------|---------|
| `mcp_bridge_url` | `http://10.0.50.12:8003/agent` | Base URL for agent API (include `/agent` suffix) |

Default if unset: `http://localhost:8003/agent` (only valid when bridge listens on SOAR localhost).

### Bridge host

- Run MCP server with builder agent routes enabled (see upstream `mcp-for-splunk` install docs).
- **LLM (pick one):**
  - **Public cloud:** `OPENAI_API_KEY` for OpenAI / compatible hosted API.
  - **On-prem / private:** `OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL` pointing at an internal OpenAI-compatible endpoint (Ollama, vLLM, LiteLLM). See **[ON_PREM_LLM.md](./ON_PREM_LLM.md)**.
- Keys and base URL live **on the bridge host only** — not on the SOAR asset.
- Optional: SOAR/Splunk credentials on bridge for IDE tool use — **not** required for sidecar chat proxy.

---

## HTTP endpoints used by the SOAR app

All requests originate from `playbook_builder_connector.py` using Python `urllib` (server-side).

### 1. Health check

| | |
|--|--|
| **Method** | `GET` |
| **URL** | `{mcp_bridge_url}` with `/agent` replaced by `/agent/health` |
| **Example** | `http://10.0.50.12:8003/agent/health` |
| **Used by** | `test connectivity` action, `?action=bridge_status`, sidecar status pill |

**Success:** HTTP 200, JSON body (bridge implementation-defined).  
**Failure:** Sidecar shows **Templates only**; chat may use local NL fallback.

### 2. Chat / NL build (primary proxy)

| | |
|--|--|
| **Method** | `POST` |
| **URL** | `{mcp_bridge_url}/api/chat` |
| **Example** | `http://10.0.50.12:8003/agent/api/chat` |
| **Request body** | JSON |

```json
{
  "message": "Build a playbook that blocks the source IP on the firewall when severity is high",
  "context": {
    "container_id": "12345",
    "playbook_id": "",
    "soar_base_url": "https://soar.example.com"
  }
}
```

`context` fields come from sidecar query params and SOAR request host (see `_chat_context_from_request`).

**Response:** JSON in **builder shape** (same as local scaffold):

- `status`, `source`, `preview`, `pattern`, `analysis`, optional `content` / assistant message
- Bridge may attach visual fields consumed by `attach_visual_preview()` on SOAR if not already present

**Timeout:** ~25s for GET chat proxy path; errors surface in sidecar chat.

### 3. Draft cache seed (optional, best-effort)

| | |
|--|--|
| **Method** | `POST` |
| **URL** | `{mcp_bridge_url}/api/draft` |
| **When** | After local **scaffold** succeeds (pattern library), to align multi-turn refine on bridge |
| **Body** | `{"context": {...}, "source": "<python source>"}` |
| **Failure** | Ignored silently — import still works |

### 4. Direct proxy route (advanced)

| | |
|--|--|
| **SOAR route** | `POST /rest/handler/<directory>/<asset>/proxy_chat` |
| **Behavior** | Forwards POST body to `{mcp_bridge_url}/api/chat` unchanged |

Most deployments use `/chat` only; `proxy_chat` exists for integrations and debugging.

---

## Sidecar → SOAR → MCP sequence (chat)

1. Analyst types in sidecar **Chat** and submits.
2. Browser `fetch`es **same-origin**  
   `GET/POST …/rest/handler/<directory>/<asset>/chat?message=…` (credentials: SOAR session).
3. Connector `_handle_chat_api`:
   - If message matches a **local pattern command** → `scaffold_pattern()` on SOAR (no MCP).
   - Else builds `body = { message, context }` and calls `_proxy_chat_to_bridge(body, mcp_bridge_url)`.
4. Bridge `/agent/api/chat` runs NL build (rules and/or LLM), returns JSON.
5. Connector `_enrich_builder_payload()` adds SOAR deep links (`soar_links`), preview enrichment.
6. Sidecar renders preview; **Import** still runs **locally** on SOAR via `import_draft` (no MCP required for import).

```
Browser          SOAR connector              MCP bridge
   |                  |                          |
   |-- chat message ->|                          |
   |                  |-- POST /agent/api/chat ->|
   |                  |<- JSON source/preview ---|
   |<- enriched JSON -|                          |
   |                  |                          |
   |-- import_draft ->| (local import_playbook)  |
   |<- playbook id ---|                          |
```

---

## Fallback when MCP is unavailable

Order of operations for a free-text chat message:

1. **Pattern command** parsed locally → scaffold on SOAR.
2. **POST to MCP** `/agent/api/chat`.
3. If bridge error or empty payload → **`try_local_build()`** in `local_nl_build.py` (keyword → pattern).
4. If still no payload → error returned to sidecar.

So Mode B degrades toward Mode A automatically; analysts can always use **Generate template** explicitly.

---

## Bridge status in the UI

On load, sidecar calls:

```
GET …/chat?action=bridge_status
```

Connector `_probe_mcp_bridge()` hits `/agent/health` from the **SOAR server**. Pill display:

| Pill | Meaning |
|------|---------|
| **AI connected** | Health check succeeded |
| **Templates only** | Health check failed — use pattern library |
| **Checking…** | In flight |

This reflects reachability **from SOAR**, not from the analyst workstation.

---

## Test connectivity action

SOAR asset action **test connectivity**:

1. Reads `mcp_bridge_url` from asset config.
2. `GET` `{base}/agent/health`.
3. Returns success with sidecar URL hint, or failure with exception text.

Use this from SOAR (not curl from your laptop) to validate production networking.

---

## Mode B setup checklist

1. Install and start MCP agent bridge on bridge host.
2. From **SOAR server** shell:  
   `curl -sS http://<bridge>:8003/agent/health`
3. Set asset `mcp_bridge_url` to `http://<bridge>:8003/agent` (or HTTPS URL).
4. Run **Test connectivity** on the asset.
5. Open sidecar — confirm **AI connected**.
6. Send NL chat message; confirm preview updates.
7. **Import to SOAR** — confirms import path still local.

---

## Security checklist (Mode B)

- [ ] LLM API keys and **`OPENAI_BASE_URL`** only on bridge host (env / secrets manager)
- [ ] Firewall: allow **SOAR → bridge** only; for on-prem LLM, allow **bridge → internal LLM** (no public internet required)
- [ ] No bridge port on `0.0.0.0` without TLS + auth in production
- [ ] Review LLM data handling (playbook source + chat in requests to the configured LLM endpoint)
- [ ] On-prem LLM: complete [ON_PREM_LLM.md](./ON_PREM_LLM.md) air-gapped checklist
- [ ] Document fallback to Mode A (clear `mcp_bridge_url` or block egress)

---

## Related docs

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Mode A vs B capabilities
- [ON_PREM_LLM.md](./ON_PREM_LLM.md) — private / on-prem LLM (OpenAI-compatible API)
- [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md) — install and operate
- [ATTRIBUTION.md](../ATTRIBUTION.md) — upstream MCP credit
- [CUSTOMIZATION.md](./CUSTOMIZATION.md) — extend patterns without changing MCP contract
