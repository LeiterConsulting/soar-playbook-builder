# What's new — plain English (v2.21–2.24)

This page explains recent Playbook Builder updates without jargon. For technical detail on the air-gap roadmap, see [AIR_GAP_BUILD_SPEC.md](./AIR_GAP_BUILD_SPEC.md).

---

## Growing & customizing templates (v2.24)

**What changed:** Help now has a **Growing & Customizing Templates** chapter. The Templates panel on Build shows a count like `11 built-in · 2 org` and a footnote explaining how to add more. `CUSTOMIZATION.md` ships inside the app on SOAR.

**Why it matters:** Eleven built-in patterns are a starter set, not the whole
product. Admins can paste strict, declarative organization IR into
`custom_ir_templates_json` without rebuilding the `.tgz`. Analysts see
`[Org]` and `Strict IR` badges and can run deterministic review; import remains
locked pending live qualification. Legacy Python templates are disabled by
default.

**Example:** Your team exports a VPE playbook, wraps it in org JSON with `nl_keywords`, pastes into the asset, refreshes the sidecar — the new pattern appears under Organization with offline NL routing.

See [CUSTOMIZATION.md](./CUSTOMIZATION.md) and `sample_data/sample_org_templates.json`.

---

## Demo data & Run Lab Testing (Help tab)

**What changed:** The Help chapter is now titled **Demo Data & Run Lab Testing** (was “Run tab testing”).

**Why it matters:** On a fresh SOAR install you often have no real security cases yet. The app ships five practice cases (IDs **9001–9005**) — fake incidents like phishing, failed logins, and a tiny “hello” smoke test. On the **Run** tab you pick a sample and click **Create on SOAR** to spin up a real container you can run playbooks against, without Splunk ES or live notables.

**Example:** An analyst installs the app in a lab, opens Run → picks case **9005 (hello)**, creates it on SOAR, builds the hello template, imports, and runs — full loop in minutes.

See [RUN_TAB_DEMO.md](./RUN_TAB_DEMO.md) for the step-by-step walkthrough.

---

## Smarter natural-language routing (v2.21)

**What changed:** Complex prompts (e.g. “PagerDuty + Teams + wait for analyst approval”) no longer get mis-routed to a single generic template like ES Notable Response when the MCP bridge or LLM is available.

**Why it matters:** Before, asking for a multi-tool workflow could silently return the wrong scaffold. Now the app recognizes “this is too specific for a keyword template” and sends it to the AI path (or tells you honestly when AI is not configured).

**Example:**  
*“Build a playbook that creates a PagerDuty incident, posts to Microsoft Teams, and waits for analyst approval before containment.”*  
→ Should produce a custom draft or structured plan, **not** the ES Notable one-size-fits-all template.

---

## Bridge status vs AI status (v2.21)

**What changed:** The header pill now distinguishes:

| Pill | Meaning |
|------|---------|
| **AI connected** | MCP bridge reachable **and** LLM API configured |
| **Bridge online · no LLM** | Bridge works, but no API key / model endpoint — custom NL falls back to stubs/templates |
| **Offline mode** | No bridge — use templates and offline keyword build |

**Why it matters:** “Bridge online” used to look like everything was ready for natural language. It wasn’t — you could still get template-only answers. The UI now matches reality.

**Example:** Bridge container is up but `OPENAI_API_KEY` is missing → pill says **Bridge online · no LLM**, and Environment shows how to fix it.

---

## Capability index — “what can my SOAR actually do?” (v2.22)

**What changed:** New module that **reads your SOAR instance** (installed apps, actions, configured assets) and saves a local catalog. Shipped with a **baseline** snapshot of common apps (ServiceNow, Slack, PagerDuty, Teams, VirusTotal, built-in phantom actions) for offline use.

**New SOAR actions:**

| Action | What it does |
|--------|----------------|
| **rebuild capability index** | Refreshes the catalog from local SOAR REST |
| **capability index status** | Shows version, app/action counts, whether the index is stale |

**Why it matters:** This is the foundation for **air-gapped** playbook building. Future versions will use this catalog — not the AI’s memory — to know whether “create PagerDuty incident” is actually installed and configured on *your* SOAR. No internet required.

**Example:** You ask for VirusTotal enrichment in an offline site. The index knows VT needs outbound internet (`requires_egress: true`) and can suggest a local custom-list lookup instead — instead of generating a playbook that fails at runtime.

The **Environment** menu now includes a **Capability index** row with a rebuild hint if you haven’t run harvest yet.

---

## Air-gap build spec & agent instructions (v2.22)

**What changed:** Full engineering spec copied to [AIR_GAP_BUILD_SPEC.md](./AIR_GAP_BUILD_SPEC.md), with [AGENTS.md](../AGENTS.md) and a Cursor rule for incremental implementation (IR → compiler → validator → eval → LLM).

**Why it matters:** Documents the long-term direction: AI proposes a structured plan (IR), deterministic code generates the playbook, and validation reports exact gaps (“ServiceNow app not installed — transfer this package”).

**Example (future):** “Block this IP on Palo Alto” when PAN is not installed → structured report with install steps, not a broken playbook.

---

## Operating mode setting (v2.22, preparatory)

**What changed:** New asset config `operating_mode`: `air_gapped` | `restricted` | `connected` (default).

**Why it matters:** Plumbs the config for step 4 (validator). In `air_gapped` mode, egress-dependent actions will be flagged or substituted automatically.

---

## How to verify after upgrade

1. Reinstall or upgrade to **2.22.0** `.tgz`.
2. Run SOAR action **rebuild capability index** once.
3. Open sidecar → Environment → confirm **Capability index** shows app/action counts.
4. Help tab → **Demo Data & Run Lab Testing** → try sample **9005**.
5. For NL: confirm bridge pill matches your LLM setup; retry a PagerDuty + Teams prompt.

Automated checks (developers):

```bash
python3 tests/test_capability_index.py
python3 soar_playbook_builder/eval/harness.py --suite capability
```
