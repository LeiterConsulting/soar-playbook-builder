# Run tab demo walkthrough

End-to-end testing on a fresh SOAR install using **built-in demo data** — no ES export, live notables, or pre-existing containers required.

**Related:** [DEMO_AND_NL_ENV.md](./DEMO_AND_NL_ENV.md) · [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md) · [EXAMPLE_WALKTHROUGHS.md](./EXAMPLE_WALKTHROUGHS.md) (Walkthrough 7)

---

## What ships with the app

| Asset | Purpose |
|-------|---------|
| **Sample cases 9001–9005** | Metadata rows in Run → Cases (always available; no asset config required) |
| **Runtime fixtures** | Container + artifact payloads used by **Create on SOAR** |
| **`sample_data/sample_cases.json`** | Bundled copy for optional `sample_cases_json` asset overrides |

Sample cases are **not** real SOAR containers until you click **Create on SOAR**. Linking a sample ID without provisioning will break Run on case.

---

## Sample catalog

| ID | Fixture | Tier | Best for |
|----|---------|------|----------|
| **9005** | `hello` | safe | Fastest Build → Import → Run smoke test |
| **9002** | `phishing-enrichment` | safe | Showcase enrichment + safe actions |
| **9004** | `es-notable-response` | safe | ES-style notable, note-only response |
| **9001** | `failed-logins-okta` | destructive | Lab — Okta disable path |
| **9003** | `insider-threat-ad` | destructive | Lab — AD containment path |

Rows marked **demo pick** in the UI are recommended for first-time installs.

---

## 10-minute smoke test

1. Install app → create Playbook Builder asset → open sidecar **Build** tab.
2. **Templates** → load `hello` → **Import to SOAR**.
3. **Run** tab → expand **Cases** → sample **9005** → **Create on SOAR** → confirm.
4. **Readiness** → fix any integration mapping → **Run on this case**.
5. Open the case in SOAR and confirm playbook execution / notes.

Repeat with **9002** or **9004** to exercise richer fixtures.

---

## Mock dev mode (no SOAR)

```bash
cd sidecar-ui && npm install && npm run dev
```

Mock API serves the same five samples, provision flow, and environment checks. Use **Run** tab quick buttons for 9005 / 9002.

---

## Optional: org-specific samples

Paste or merge entries from `soar_playbook_builder/sample_data/sample_cases.json` into the asset field **`sample_cases_json`**. Custom rows merge with built-in defaults; duplicate IDs override catalog entries.

Each row should include:

- `id` (numeric, use 9xxx for demos)
- `name`, `severity`, `label`, `event_id`, `rule_name`
- `fixture_pattern_id` matching a key in `runtime_fixtures.py`
- `demo_tier`: `safe` | `destructive` | `integration`
- `showcase_recommended`: `true` to highlight in UI

---

## API reference

| Action | Purpose |
|--------|---------|
| `list_cases` | Sample + live SOAR cases |
| `provision_demo_case` | `sample_id` + `confirm=1` → real container |
| `readiness_check` | Pre-run gate with linked container |
| `environment_check` | Confirms demo fixtures + sample count |

See [DEMO_AND_NL_ENV.md](./DEMO_AND_NL_ENV.md) for environment self-healing.
