# Fresh install & migration — turnkey walkthrough

Move Playbook Builder to a **new SOAR instance** (lab rebuild, customer handoff, or disaster recovery). Most of the product ships inside the `.tgz`; you only re-enter **asset settings** and optionally re-import **playbooks you authored**.

**Related:** [PLAYBOOK_BUILDER_GUIDE.md](./PLAYBOOK_BUILDER_GUIDE.md) · [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) · [RUN_TAB_DEMO.md](./RUN_TAB_DEMO.md) · [WHATS_NEW_PLAIN_ENGLISH.md](./WHATS_NEW_PLAIN_ENGLISH.md)

---

## How easy is redeploy?

| Scenario | Effort | Typical time |
|----------|--------|--------------|
| **Mode A — templates only** (no MCP/LLM) | Low | **15–20 min** |
| **Mode B — MCP bridge + LLM** | Medium | **30–60 min** (bridge + firewall + asset) |
| **Plus ES/Mission Control stitch** | Medium+ | Add **30 min** for URLs and utility playbooks |

**Good news:** You do **not** migrate databases or custom servers. Install one app file, create one asset, run two SOAR actions, smoke-test with built-in demo case **9005**.

**What does *not* auto-migrate:** Asset configuration (URLs, API keys, integration name maps), playbooks you imported on the old SOAR, and the capability index (rebuilt locally on each instance).

---

## What ships in the app (no migration needed)

These come with every `soar_playbook_builder.tgz` install:

| Included | Notes |
|----------|--------|
| Sidecar UI (Build / Run / Help) | Static widgets — no separate web server |
| 11+ playbook templates | Hello, Okta, ClearPass, ES notable, etc. |
| Demo sample cases **9001–9005** | Create on SOAR from Run tab |
| Runtime fixtures | Used when provisioning demo containers |
| Capability baseline | Common apps/actions for offline use |
| Help guides | In-app setup, demo lab, NL recovery, troubleshooting |
| `sample_data/sample_cases.json` | Optional override via `sample_cases_json` on asset |

---

## What you must reconfigure on the new SOAR

Copy these from your **old Playbook Builder asset** (SOAR UI → Apps → asset → Configuration) before the lab shuts down:

| Asset field | Required? | Example | Why |
|-------------|-----------|---------|-----|
| `mcp_bridge_url` | Mode B only | `http://10.0.0.5:8003/agent` | Update if SOAR hostname/network changed |
| `ai_instructions` | Optional | `SOC — classic Python playbooks` | Header text in sidecar |
| `asset_defaults` | Recommended | `{"okta":"okta","slack":"slack_lab"}` | Maps template placeholders → your assets |
| `playbook_defaults_json` | Optional | Constants + extra asset maps | Readiness auto-fix |
| `custom_templates_json` | Optional | Org-specific templates | Your `org-*` patterns |
| `es_web_url` | ES stitch | `https://es.example.com:8000` | Back to Mission Control links |
| `soar_rest_token` | Optional | REST token | Sidecar import when session loopback fails |
| `sample_cases_json` | Optional | Extra demo rows | Merged with built-in 9001–9005 |
| `operating_mode` | Optional | `connected` / `air_gapped` | Air-gap validator (future steps) |

**Tip:** Screenshot or export the asset configuration JSON before decommission. SOAR REST `GET /rest/asset/<id>` also works.

**Playbooks:** Export any playbooks you care about from the old SOAR (Playbooks → export) and re-import on the new instance — they are SOAR objects, not part of the Playbook Builder app package.

---

## Turnkey install — Mode A (templates only)

Use this for air-gapped labs or when MCP is not ready yet.

### 1. Install the app (~2 min)

```bash
# On your build machine (or use a pre-built artifact)
cd packaging/soar-playbook-builder-app
./package_app.sh
# → dist/soar_playbook_builder.tgz
```

On new SOAR: **Apps → Install App** → upload `soar_playbook_builder.tgz`.

### 2. Create & configure asset (~5 min)

1. **Apps → SOAR Playbook Builder → Create Asset** (e.g. `playbook_builder`).
2. Set `ai_instructions` (optional).
3. Leave `mcp_bridge_url` **empty** for Mode A.
4. Paste saved `asset_defaults` if you had them on the old lab.
5. Save.

### 3. Run setup actions (~3 min)

On the asset, run in order:

| Action | Expected |
|--------|----------|
| **get sidecar url** | Returns handler URL — bookmark it |
| **rebuild capability index** | Success with app/action counts (uses local SOAR REST) |
| **capability index status** | `loaded: true`, not stale |

### 4. Open sidecar & verify environment (~2 min)

1. Open the sidecar URL in a browser (logged into SOAR).
2. Click the **status pill** in the header → Environment.
3. Confirm: Capability index row, Demo cases row.
4. Optional: **Fix environment** if asset_defaults can be auto-discovered.

### 5. Smoke test with demo case 9005 (~5 min)

1. **Run** tab → sample **9005 (hello)** → **Create on SOAR**.
2. **Build** tab → Templates → **Hello World** → Load template → Import.
3. **Run** tab → **Run on this case**.

If all three tabs work, Mode A is **turnkey complete**.

---

## Turnkey install — Mode B (MCP + LLM)

Everything in Mode A, plus:

### Bridge host

1. Install MCP agent bridge on a host **SOAR can reach** (not the analyst laptop unless tunneled).
2. Configure LLM: `OPENAI_API_KEY` (cloud) or `OPENAI_BASE_URL` + `AGENT_BRIDGE_MODEL` (on-prem) — see [ON_PREM_LLM.md](./ON_PREM_LLM.md).
3. Confirm `GET …/agent/health` returns OK from the bridge host.

### Asset

1. Set `mcp_bridge_url` to e.g. `http://<bridge-host>:8003/agent`.
2. Run **test connectivity** on the asset → success.
3. Sidecar pill should show **AI connected** (not just “Bridge online · no LLM”).

### NL smoke test

Build tab → Natural Language → try a simple prompt: *“Build an Okta failed login response playbook.”*

---

## Migrating from your current lab (checklist)

Before shutdown:

- [ ] Save `dist/soar_playbook_builder.tgz` (or rebuild from source tag **v2.22.0**).
- [ ] Export Playbook Builder **asset configuration** (all JSON fields above).
- [ ] Export any **custom playbooks** authored via the builder.
- [ ] Note **MCP bridge** host, port, and LLM env vars.
- [ ] Note **ES web URL** and any response-plan / utility playbook setup ([ES_SOAR_BUILDER_STITCH.md](./ES_SOAR_BUILDER_STITCH.md)).

On new SOAR:

- [ ] Install `.tgz` → create asset → paste saved config.
- [ ] Run **rebuild capability index** + **get sidecar url**.
- [ ] Mode B: **test connectivity** + confirm **AI connected** pill.
- [ ] Run tab demo **9005** end-to-end.
- [ ] Re-import exported playbooks if needed.
- [ ] Re-run ES stitch steps if Mission Control integration applies.

---

## Automated validation (optional)

From a machine that can reach the new SOAR:

```bash
cd packaging/soar-playbook-builder-app
SOAR_URL=https://new-soar:8443 SOAR_USER=... SOAR_PASS=... ASSET=playbook_builder \
  ./scripts/print_sidecar_url.sh

# Full E2E (requires httpx + credentials)
./scripts/run-e2e-validate.sh auto
```

See [E2E_VALIDATION.md](./E2E_VALIDATION.md).

---

## In-app guided setup

After install, open the sidecar **Help** tab:

1. **Setup assistant** — rebuild index, self-test, export config (one-click)
2. **First-Time Setup & Migration** — full checklist
3. **Environment** menu (header) — same setup actions on any tab

Bundled on SOAR at `soar_playbook_builder/docs/FRESH_INSTALL_AND_MIGRATION.md`.

---

## Delivered in v2.23.0

| Feature | Status |
|---------|--------|
| Setup assistant (Help tab) | Shipped |
| Export / import asset config | Shipped (SOAR actions + sidecar) |
| Run self-test action | Shipped |
| Key docs bundled in `.tgz` | Shipped |

## Roadmap (future)

- Import asset config from sidecar file picker (paste JSON today via SOAR action)
- Post-install playbook on app enable
- Full first-run wizard modal on first sidecar open

Today, the **15-minute Mode A path** above is the supported turnkey flow.
