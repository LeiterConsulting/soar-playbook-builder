# Attribution & third-party components

## SOAR Playbook Builder (this package)

The **SOAR Playbook Builder** is a custom Splunk SOAR application (`soar_playbook_builder`). It is **not** a Splunk product, Splunkbase listing, or official Splunk-supported app unless separately published and certified by Splunk.

Copyright and license: see `soar_playbook_builder/soar_playbook_builder.json` (`license`: Apache 2.0).  
Customize `publisher` in the manifest before distributing under your organization’s name.

---

## Optional MCP agent bridge (Mode B only)

Mode A (templates, validate, import) runs **entirely on SOAR** and does not require MCP.

Mode B proxies natural-language chat from the SOAR app to an **MCP agent bridge** running on infrastructure **you** operate. That bridge is **not** included in `soar_playbook_builder.tgz`.

### Community MCP server

The reference bridge implementation builds on the community project:

**[mcp-for-splunk](https://github.com/deslicer/mcp-for-splunk)** — Model Context Protocol server for Splunk (and related plugins).

- License: Apache 2.0 (see upstream repository)
- Maintainers: community / Deslicer ecosystem (not Splunk Inc.)

There is **no official “Splunk SOAR MCP” product** from Splunk. Integration is: custom SOAR app → HTTP → customer-run MCP bridge → optional LLM provider.

### Related upstream packages (bridge host)

When installing Mode B, operators typically use packages from the same ecosystem:

| Package | Role |
|---------|------|
| `mcp-server-for-splunk` (parent server) | MCP HTTP transport, Splunk toolsets |
| `mcp-soar-server` | SOAR REST helpers on the bridge (optional for IDE use) |
| Builder bridge plugin | Agent HTTP routes (`/agent/api/chat`, `/agent/health`, …) |

Exact package names and install commands may change; follow the bridge host README in your MCP distribution.

### LLM providers

If `OPENAI_API_KEY` (or another provider) is configured **on the bridge host**, chat text and generated playbook source may be sent to that provider. Splunk and this SOAR app do not host or endorse a specific LLM vendor — that is a **customer policy and contract** decision.

---

## What this repository does not claim

- No affiliation with Splunk Inc. beyond use of the SOAR app platform APIs  
- No bundled Splunk Enterprise Security content or sample datasets  
- No pre-configured third-party SaaS credentials (Okta, ServiceNow, etc.)  

Customers supply their own SOAR instance, connectors, cases, and bridge/LLM configuration.

---

## Suggested notice for your fork / GitHub README

> **Third-party MCP:** Optional natural-language features use a community [MCP for Splunk](https://github.com/deslicer/mcp-for-splunk) agent bridge running on customer-controlled infrastructure. Splunk does not ship this bridge as part of SOAR.
