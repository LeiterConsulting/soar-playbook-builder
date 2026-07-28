# End-to-end validation guide

Run this **before publishing to GitHub** or handing the app to a customer. It validates the production Playbook Builder on **your** SOAR instance — no bundled sample data.

For **manual NL / operator recovery testing** (unsupported prompts, Readiness gaps, recovery loop flowchart), also complete [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md).

| Deliverable | Purpose |
|-------------|---------|
| **Automated runner** | `scripts/run-e2e-validate.sh` |
| **HTML report** | `dist/e2e/e2e-report.html` — clickable verify links |
| **This guide** | What each step does and how to confirm it manually |

---

## Quick start

### Option A — Validation console (recommended)

Interactive React UI with **Run** buttons, live streaming results, and **Verify ↗** fly-out links:

```bash
cd soar-playbook-builder
cp scripts/env.e2e.example scripts/env.e2e.local   # edit credentials
chmod +x scripts/run-e2e-console.sh
./scripts/run-e2e-console.sh
```

Open **http://127.0.0.1:5174** — walk phases in the sidebar, click **Validate entire app** or **Run this phase only**.

### Option B — CLI only

```bash
cd soar-playbook-builder
cp scripts/env.e2e.example scripts/env.e2e.local
# Edit SOAR_URL, credentials, PB_ASSET, MCP_BRIDGE_URL
```

Or point at MCP monorepo `.env`:

```bash
export E2E_ENV=~/mcp-for-splunk/.env
export SOAR_VERIFY_SSL=false
export PB_ASSET=mcpbridge
```

### 2. Run automated validation

```bash
chmod +x scripts/run-e2e-validate.sh
./scripts/run-e2e-validate.sh auto          # Mode auto — full check, bridge optional
./scripts/run-e2e-validate.sh A            # Mode A only — no MCP required
./scripts/run-e2e-validate.sh B            # Mode B — MCP must be reachable from SOAR
```

Options via env:

```bash
SKIP_IMPORT=1 ./scripts/run-e2e-validate.sh A     # Skip import (read-only API tests)
KEEP_E2E_PLAYBOOK=1 ./scripts/run-e2e-validate.sh auto   # Keep imported test playbook
```

### 3. Open the report

After the run:

- **HTML:** `dist/e2e/e2e-report.html` (opens automatically on macOS)
- **Markdown:** `dist/e2e/e2e-report.md`
- **JSON:** `dist/e2e/e2e-report.json`

Exit code **0** = no errors (warnings/manual still possible). Exit code **1** = at least one error.

---

## Validation phases (what runs automatically)

Each row maps to a check in the HTML report with an **Open** link where applicable.

### Phase 1 — Prerequisites

| Check | Automation | You verify |
|-------|------------|------------|
| Environment variables | Reads `SOAR_URL`, `SOAR_USER`, `SOAR_PASSWORD` | Credentials match a SOAR admin/analyst who can install apps and import playbooks |

---

### Phase 2 — SOAR platform & app

| Check | Automation | Open link / manual verify |
|-------|------------|---------------------------|
| SOAR REST reachable | `GET /rest/version` | [SOAR home](SOAR_URL) — login works |
| App installed | Finds `soar_playbook_builder` in `/rest/app` | **Apps** UI — app enabled |
| App version | Compares to the source manifest version | Apps → version column |
| Asset exists | Finds asset by `PB_ASSET` name | Asset page — `mcp_bridge_url`, `ai_instructions` |

**Typical URLs** (replace placeholders):

| Link | Pattern |
|------|---------|
| SOAR home | `https://<soar>/` |
| Apps | `https://<soar>/mission/#/apps` |
| Sidecar | `https://<soar>/rest/handler/<directory>/<asset>/chat` |
| App REST | `https://<soar>/rest/app` |

Get sidecar URL:

```bash
SOAR_URL=... SOAR_USER=... SOAR_PASS=... ASSET=mcpbridge ./scripts/print_sidecar_url.sh
```

---

### Phase 3 — Sidecar API (Mode A core)

These prove **localized** builder functionality on SOAR without MCP.

| Check | Automation | Open link — expect |
|-------|------------|-------------------|
| Sidecar HTML | `GET …/chat` | Browser sidecar — Playbook Builder UI loads |
| Hello scaffold | `POST …/chat` with `{"action":"scaffold","pattern":"hello"}` | JSON with `source` + `preview` |
| Validate | `POST …/chat` with `{"action":"validate","pattern":"hello"}` | JSON with `analysis.score` |
| Builder steps | `GET …/chat?action=steps` | JSON list of guided steps |

**Manual sign-off:** In the browser sidecar:

1. Select **Hello World** → **Generate template**
2. **Blocks** and **Code** tabs populate
3. **Validate** — score shown
4. Status pill: **Templates only** (Mode A) or **AI connected** (Mode B)

---

### Phase 4 — Import pipeline

| Check | Automation | Open link — expect |
|-------|------------|-------------------|
| Import Hello | `POST …/chat` `action=import_draft`, `confirm=true` | New playbook `PB_E2E_Hello_<timestamp>` |
| REST playbook | `GET /rest/playbook/{id}` | Playbook metadata JSON |
| Cleanup | `DELETE /rest/playbook/{id}` unless `KEEP_E2E_PLAYBOOK=1` | Playbook removed from list |

**Manual sign-off:**

| Link | Expect |
|------|--------|
| `https://<soar>/playbook/<id>?editor=visual` | Visual Editor opens imported Hello playbook |
| Playbooks list | Playbook name matches import confirmation |

Use `SKIP_IMPORT=1` if you cannot create playbooks in the target environment.

---

### Phase 5 — MCP bridge (Mode B)

| Check | Automation | Open link — expect |
|-------|------------|-------------------|
| Bridge from SOAR | `GET …/chat?action=bridge_status` | `"reachable": true` when Mode B configured |
| MCP health (runner) | `GET {MCP_BRIDGE_URL}/../health` | JSON `status: ok` |
| NL chat proxy | `POST …/chat` with NL message (Mode B only) | JSON with `source` or `preview` |

**Critical:** Bridge status uses the **SOAR server’s** network path, not your laptop.

Verify from **SOAR server shell**:

```bash
curl -sS "http://<bridge-host>:8003/agent/health"
```

Asset `mcp_bridge_url` must match what SOAR can reach (see [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)).

**Manual sign-off:**

| Step | Where | Expect |
|------|-------|--------|
| Test connectivity | Asset → **test connectivity** action | Success + sidecar URL in message |
| Sidecar pill | Sidecar header | **AI connected** |
| Chat | Type open-ended NL prompt | Preview updates |

---

### Phase 7 — Runtime vet (all templates)

After import works (Phase 4), vet **every** template structurally and optionally run playbooks on SOAR:

```bash
pip install -r scripts/requirements-validate.txt
python3 scripts/runtime_validate.py                    # offline — 11 templates
source scripts/env.e2e.local
./scripts/run-runtime-validate.sh --live --mode safe   # hello + enrichment templates
./scripts/run-runtime-validate.sh --live --mode safe --transport mcp   # when MCP stack ready
```

See [RUNTIME_VALIDATION.md](./RUNTIME_VALIDATION.md) for integration/destructive tiers.

---

### Phase 6 — Manual sign-off (required before GitHub)

The automation marks these **◎ manual** — you must confirm in the UI:

| Item | Link | Pass criteria |
|------|------|---------------|
| Sidecar UI | Sidecar URL | Layout, buttons, no JS errors in devtools |
| Test connectivity | Apps → asset | Action succeeds |
| Visual Editor | Playbooks → imported playbook | Correct playbook opens after import |
| Cleanup | Playbooks list | Remove `PB_E2E_*` if `KEEP_E2E_PLAYBOOK=1` was used |

---

## Recommended sign-off sequence

Use this order the first time you validate a new build:

```text
1. ./package_app.sh && install .tgz on SOAR
2. Create asset (PB_ASSET)
3. ./scripts/run-e2e-validate.sh A        → Mode A must be green
4. Complete Phase 6 manual checks in HTML report
5. (Optional) Configure MCP → ./scripts/run-e2e-validate.sh B
6. Complete Mode B manual checks
7. Tag release only when: errors=0 and manual items checked
```

---

## Mode reference

| Mode | Command | MCP required | Use when |
|------|---------|--------------|----------|
| **A** | `run-e2e-validate.sh A` | No | Air-gap sign-off, GitHub CI against lab |
| **B** | `run-e2e-validate.sh B` | Yes | Full NL + LLM path |
| **auto** | `run-e2e-validate.sh auto` | Optional | Pre-release; bridge failures = warn |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| SOAR REST error | VPN / wrong URL / creds | Fix `SOAR_URL`, `SOAR_VERIFY_SSL=false` for lab |
| App not found | `.tgz` not installed | Install `dist/soar_playbook_builder.tgz` |
| Sidecar 404 | Wrong `directory` in URL | Run `print_sidecar_url.sh` |
| Scaffold empty | Old app version | Rebuild/install the version declared in the source manifest |
| Import fails | SCM / permissions | SOAR logs; user needs import rights |
| Bridge OK on laptop, fail on SOAR | Network path | curl health **from SOAR server** |
| Templates only in Mode B | Asset URL wrong or bridge down | Fix `mcp_bridge_url`, restart bridge |

---

## CI integration (optional)

```yaml
# Example job snippet — run from the repository root
- name: E2E validate Mode A
  env:
    SOAR_URL: ${{ secrets.SOAR_URL }}
    SOAR_USER: ${{ secrets.SOAR_USER }}
    SOAR_PASSWORD: ${{ secrets.SOAR_PASSWORD }}
    SOAR_VERIFY_SSL: "false"
    PB_ASSET: playbook_builder
    SKIP_IMPORT: "1"
  run: ./scripts/run-e2e-validate.sh A
```

Upload `dist/e2e/e2e-report.html` as a workflow artifact for reviewers.

---

## Related docs

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Mode A vs B
- [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) — HTTP contract for bridge
- [REPLICATION_HANDOFF.md](./REPLICATION_HANDOFF.md) — customer checklist
