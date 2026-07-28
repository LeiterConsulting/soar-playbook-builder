# Example walkthroughs (reference)

These are **generic reference workflows** for operators learning the Playbook Builder. They use your own SOAR instance, connectors, and containers — no bundled sample data or lab IPs.

For install and architecture, see [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md) and [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Walkthrough 1 — First playbook (Mode A, templates-only)

**Goal:** Generate a minimal playbook, validate, import, and open in the Visual Editor without any external bridge.

**Prerequisites:** App installed, asset created, sidecar URL bookmarked.

1. Open the sidecar (`…/chat`).
2. Confirm status pill shows **Templates only** (bridge not required).
3. In the pattern library, select **Hello World** (or equivalent minimal pattern).
4. Click **Generate template**.
5. Review **Blocks** and **Code** tabs in the preview panel.
6. Click **Validate** — expect a passing score or actionable warnings.
7. Click **Import to SOAR** — wait for sync confirmation with playbook name and ID.
8. Click **Open in SOAR** — Visual Editor opens **your** imported playbook.

**Expected outcome:** A new classic Python playbook in your SOAR repository, editable in VPE.

---

## Walkthrough 2 — Container-aware build

**Goal:** Open the sidecar from a SOAR container context so prompts reference container metadata.

**Prerequisites:** An existing SOAR container (from your SIEM, manual creation, or any source you already use).

1. In SOAR, open a container.
2. Open the Playbook Builder sidecar with container context in the URL (your org may use a custom menu link):
   ```
   https://<soar>/rest/handler/<directory>/<asset>/chat?container_id=<CONTAINER_ID>
   ```
3. Note the header shows container context when supported.
4. Select a pattern relevant to your environment (e.g. enrichment, ticketing, network action).
5. Generate → Validate → Import → Open in SOAR.
6. From the container **Playbooks** tab, confirm the new playbook appears and can be run per your SOAR permissions.

**Expected outcome:** Playbook imported and runnable against your container — no sample artifacts shipped with the app.

---

## Walkthrough 3 — Custom integration pattern (Mode A)

**Goal:** Use natural-language keywords that map to a built-in or customized pattern (e.g. firewall block, IdP disable, ticket create).

**Prerequisites:** Required connector apps installed in **your** SOAR (Palo Alto, Okta, ServiceNow, etc.).

1. In chat or example prompts, describe the workflow in plain language, e.g.  
   *“Build a playbook that blocks the source IP on the firewall when severity is high.”*
2. If Mode A: rule-based matching selects the closest scaffold; review and edit **Code** before import.
3. Validate — fix any connector name mismatches to match **your** installed apps.
4. Import and publish through your normal SOAR change process.

**Expected outcome:** Starter code aligned to your connectors; engineers complete credentials, app names, and error handling before production.

---

## Walkthrough 4 — Natural language with bridge (Mode B)

**Goal:** Use open-ended chat and refinement with an MCP agent bridge and optional LLM.

**Prerequisites:** Mode B configured (`mcp_bridge_url` reachable from SOAR); bridge health OK; LLM configured on bridge — **public cloud** (`OPENAI_API_KEY`) or **on-prem** (`OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL`). See [ON_PREM_LLM.md](./ON_PREM_LLM.md).

1. Run **Test connectivity** on the asset — expect bridge reachable.
2. Open sidecar — status pill **AI connected**.
3. Describe a multi-step workflow in chat (conditions, multiple actions, notes).
4. Review preview; ask a follow-up in chat (e.g. *“Add a note with artifact summary before the action”*).
5. Validate → Import → Open in SOAR.

**Expected outcome:** LLM- or bridge-assisted draft; same import path as Mode A.

**Security reminder:** Chat and source go SOAR → bridge → LLM. With an **on-prem LLM**, that path stays on the customer network. Use Mode A if no bridge/LLM is permitted.

---

## Walkthrough 5 — Customize header and prompts for your SOC

**Goal:** Set operator-facing context without code changes.

1. SOAR → Apps → SOAR Playbook Builder → your asset.
2. Set **ai_instructions** to your standard, e.g.  
   `Production SOAR — classic Python only; publish via change board #CHG-1234`
3. Save and reload sidecar — header reflects your text.

For new patterns and UI labels, see [CUSTOMIZATION.md](./CUSTOMIZATION.md).

---

## Walkthrough 6 — IDE power users (optional, Mode B)

**Goal:** Same bridge used by the sidecar is available to developers in Cursor or other MCP clients.

1. Run MCP server on the bridge host with SOAR headers configured (see PLAYBOOK_BUILDER_GUIDE).
2. Use builder/scaffold/import tools from the IDE against **your** SOAR URL.
3. Sidecar and IDE share patterns when bridge plugin versions match.

This is optional; analysts can stay entirely in the SOAR sidecar.

---

## What these walkthroughs deliberately omit

- Pre-seeded notables, BOTS, or demo containers  
- Fixed IP addresses or SSH tunnel recipes as the primary install path  
- Presenter scripts or slide decks  
- Sample Okta orgs or credential placeholders in the app package  

Your environment supplies all case data and connector configuration.

---

## Walkthrough 7 — NL stress test & recovery loop

**Goal:** Verify behavior when natural language asks for something **outside the shipped template catalog**, and practice the operator recovery path (stub → Readiness → nearest template → import/run).

**Prerequisites:** App installed (v2.18+ for Readiness on POST); sidecar on **Build** tab.

**Full guide:** [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md) — includes mermaid flowchart, gap tables, test record template, and reference prompts.

**Quick sequence:**

1. Submit the reference prompt (PagerDuty + Teams + approval gate) — expect stub or `needs_assets`, not a finished workflow.
2. Run **Readiness** — note `container_missing`, integration, and artifact items.
3. Submit recovery prompt (ServiceNow P1 incident) — expect keyword match in Mode A.
4. **Import** → map assets if blocked → **Run** tab link case → **Run on this case**.
5. Use **Help → Troubleshooting** for any errors encountered.

**Expected outcome:** Clear signals when NL outruns catalog coverage; documented path to a working import using nearest template and environment fixes.
