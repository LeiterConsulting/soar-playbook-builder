# Changelog

All notable changes to the **SOAR Playbook Builder** app (`soar_playbook_builder`) are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versioning aligns with `app_version` in `soar_playbook_builder.json`.

## [2.26.0] — 2026-07-28

### Full persona integration (ES + Splunk Enterprise + asset defaults)
- **Asset `default_ui_mode`:** Set studio | assistant | coach | tutor on the Playbook Builder asset; URL `mode=` always overrides. Sidecar reads `data-default-ui-mode` from the HTML shell.
- **`splunk_link` route:** Splunk Enterprise dashboard/alert drilldown → Response Coach (non-ES entry). Sample drilldown in `es_content/drilldown_splunk_playbook_builder.json`.
- **L1 case intel:** Coach Respond shows recent playbook runs on the linked case (`coach_case_intel.py`).
- **Utility playbook:** `open_playbook_builder.py` — `BUILDER_MODE` and `BUILDER_TAB` for coach/assistant deep links.
- **Assistant banner** on Build when `mode=assistant`; **Run on case** on Coach Respond panel.
- **Chat:** `review playbook` runs static analysis on the current draft.
- **Setup assistant** + environment check hint for persona URLs; bundled **`docs/COACH_PERSONAS.md`**.

## [2.25.0] — 2026-07-28

### Coach, Assistant & Tutor personas
- **URL modes:** `?mode=studio` (default), `assistant`, `coach`, `tutor` + coach `tab=respond|explain|build`.
- **Respond lane (L0 coach):** `coach_suggest` action — rule→template, case summary, offline deterministic.
- **Explain lane (tutor):** offline `lesson` / `quiz` / `explain` routing in connector; bundled curriculum in `tutor_local.py`.
- **Coach UI:** `/coach` route with Respond · Explain · Build tabs; ES `es_link` passes `mode` and `tab`.
- Help chapter: **Coach, Assistant & Tutor Personas**.

## [2.24.0] — 2026-07-27

### Template library growth — UI & bundled docs
- **Help chapter:** Growing & Customizing Templates — org JSON vs built-in scaffolds, migration, NL recovery tie-in.
- **Templates panel:** Header shows `N built-in · M org`; footnote links to Help and `custom_templates_json`.
- **Bundled docs:** `CUSTOMIZATION.md` ships in `.tgz` under `soar_playbook_builder/docs/`.
- **Sample data:** `sample_data/sample_org_templates.json` copy-paste example for org templates.

## [2.23.0] — 2026-07-27

### Turnkey install & migration
- **Setup assistant** on Help tab — rebuild capability index, run self-test, export asset config.
- **SOAR actions:** `export asset config`, `import asset config`, `run self test`.
- **Environment menu** — setup fix buttons (rebuild index, export, self-test) on all tabs.
- **Bundled docs** in `.tgz` under `soar_playbook_builder/docs/` (migration, run lab, handoff, etc.).
- Help order: **First-Time Setup & Migration** first; **How to Use** second.

## [2.22.0] — 2026-07-27

### Air-gap architecture — capability index (spec step 1)
- **`soar_playbook_builder/capability/`** — schema, baseline snapshot (`apps.json`, `cef.json`, `egress_tags.json`), SOAR REST introspection, merge + persist.
- **SOAR actions:** `rebuild capability index`, `capability index status`.
- **`eval/harness.py --suite capability`** — step-1 gate; **`tests/test_capability_index.py`**.
- **Docs:** [WHATS_NEW_PLAIN_ENGLISH.md](docs/WHATS_NEW_PLAIN_ENGLISH.md), [AIR_GAP_BUILD_SPEC.md](docs/AIR_GAP_BUILD_SPEC.md), [AGENTS.md](AGENTS.md), Cursor rule `.cursor/rules/air-gap-playbook-builder.mdc`.
- **Config:** `operating_mode` (`air_gapped` | `restricted` | `connected`) — used by validator in a later step.

## [2.21.0] — 2026-07-27

### NL routing — custom prompts vs keyword templates
- **Bridge status pill** now distinguishes **AI connected** (bridge + LLM) vs **Bridge online · no LLM** (reachable but no API key / base URL).
- **`/agent/health`** reports `llm_configured`, `llm_mode`, and `llm_model`; `environment_check` adds an **LLM / model API** row.
- **SOAR connector:** Skip offline keyword scaffolds when MCP bridge is reachable; complex prompts (PagerDuty, Teams, approval gates) defer to bridge/LLM.
- **MCP agent bridge (`nl_build.py`):** Same defer rules — no longer returns ES Notable (or other catalog templates) for multi-integration NL asks.
- **Mock dev (`localNlBuild.ts`):** Parity routing for `npm run dev` without SOAR.

### Demo data & Run tab
- **Five built-in sample cases** (9001–9005) with fixture mapping, demo tiers, and showcase badges.
- **Create on SOAR** workflow for samples (not Link); Run tab demo guide + quick-start buttons.
- **`sample_data/sample_cases.json`** bundled in install `.tgz` for optional `sample_cases_json` overrides.
- Docs: [RUN_TAB_DEMO.md](docs/RUN_TAB_DEMO.md); updated [DEMO_AND_NL_ENV.md](docs/DEMO_AND_NL_ENV.md).

### Help tab
- Help chapter renamed to **Demo Data & Run Lab Testing** (was “Run tab testing”).
- Plain-English summary: [WHATS_NEW_PLAIN_ENGLISH.md](docs/WHATS_NEW_PLAIN_ENGLISH.md).
- **Natural Language Testing & Recovery Loop** — in-app flowchart + recovery tiers (mirrors [NL_TESTING_AND_RECOVERY.md](docs/NL_TESTING_AND_RECOVERY.md)).

## [2.20.0] — 2026-07-27

### Layout — environment + templates
- **Environment** moved to header dropdown (click MCP bridge status) — available on all tabs.
- **Templates consolidated**: dropdown + dynamic detail panel (badges, expandable lab walkthrough & NL prompt).
- **Templates collapse**: Collapse/Expand control frees chat space; preference saved in browser.
- **Code preview**: Python syntax highlighting on Preview → Code tab.
- **Blocks preview**: Human-readable summaries per step (collect fields, action purpose, decision branches).
- **Header subtitle**: AI instructions line wraps instead of truncating with ellipsis.
- **Panel backgrounds**: Chat, templates, NL prompt, and preview pane unified to `--bg` depth.
- **Help walkthrough**: Step-by-step builder guide on Help tab (templates → preview → import → run).
- Removed separate Wizard panel and quick-start chip row.

## [2.19.0] — 2026-07-27

### UI — Splunk SOAR / Dashboard Studio visual refresh
- Dark chrome with Splunk pink accent bar, Inter typography, and card-based panels.
- SOAR-style tab navigation and workflow stepper with status markers.
- Environment panel: proper section spacing, working **Refresh** with timestamp feedback.
- Build footer: Environment separated from Templates / Wizard / NL authoring block.

## [2.18.0] — 2026-07-27

### One-click Fix environment
- **`apply_environment_fixes`** — discovers installed SOAR assets and writes `asset_defaults` on the Playbook Builder asset.
- **Fix environment** button on the Build tab environment banner (when defaults are missing but integrations exist).
- POST handler routes all builder actions (not only `chat` / `import_draft`) so provision and fix actions work from the sidecar.

## [2.17.0] — 2026-07-27

### Demo data and NL environment self-healing
- **Create on SOAR** on sample cases — provisions real containers + artifacts from runtime fixtures (`provision_demo_case`).
- **Environment banner** on Build tab — MCP bridge status, checks, and one-click **Use template** / **Retry bridge**.
- **`environment_check`** action — structured readiness for NL (bridge, asset defaults, demo fixtures).
- Offline NL responses include `offline_mode` and `suggested_pattern` for template fallback.
- Docs: `docs/DEMO_AND_NL_ENV.md`.

## [2.16.2] — 2026-07-27

### Fix — no more repeating chat / panels
- Boot no longer re-runs when you link a case (was re-posting mock/workflow/offline messages).
- Case context updates the header only — not duplicated into chat.
- **Cases** and **Help** live on the Run tab only (removed from Build footer and Import bar).

## [2.16.1] — 2026-07-27

### UI — clearer sections, less copy
- Unified **bordered panels** (`app-section`) for Cases, Templates, Wizard, NL chat, Import, and Run actions.
- Stronger column dividers; chat and preview areas boxed separately.
- Shorter labels throughout (workflow strip, help, readiness, case picker).

## [2.16.0] — 2026-07-27

### Case picker — pull cases into the builder
- **`list_cases` API** — returns recent SOAR containers plus built-in **sample demo cases** (failed logins, phishing, insider threat).
- Sidecar **Pick a case** panel on **Run** and **Build** tabs: browse, filter, **Link case** (updates URL `container_id` and hydrates investigation context).
- Sample cases work in mock dev mode and on SOAR when container IDs match `sample_data/sample_cases.json`.
- Optional asset field **`sample_cases_json`** to add org-specific demo cases.

## [2.15.0] — 2026-07-27

### Sidecar SPA (React Router + mock dev)
- Sidecar UI rebuilt as a **HashRouter SPA** with **Build**, **Run on case**, and **Help** routes.
- **`npm run dev`** works without SOAR via mock API (templates, scaffold, NL chat, import, run).
- Optional live SOAR: set `VITE_SOAR_HANDLER_BASE` in `.env.local`.
- Code split: `BuilderProvider` context, pages, `ActionBar` component.

## [2.14.1] — 2026-07-27

### ES round-trip + auto-open on export
- Asset field **`es_web_url`** — sidecar header shows **Back to Mission Control** when `event_id` is in the URL.
- Response plan guide + template: [docs/RESPONSE_PLAN_OPEN_BUILDER.md](docs/RESPONSE_PLAN_OPEN_BUILDER.md), `soar_content/response_plan_open_playbook_builder.json`.
- Smoke test: `python3 scripts/smoke_test_stitch.py`.

## [2.14.0] — 2026-07-27

### ES ↔ SOAR ↔ Builder stitching
- New REST route **`es_link`** — ES drilldown target; resolves SOAR case from `event_id` and redirects to the sidecar with full context.
- Shipped **Open Playbook Builder** utility playbook (`dist/open_playbook_builder.tgz`) — runs `get sidecar url` with `container.id` + ES artifact hints.
- Guide: [docs/ES_SOAR_BUILDER_STITCH.md](docs/ES_SOAR_BUILDER_STITCH.md) and sample ES drilldown in `es_content/`.

## [2.13.1] — 2026-07-27

### Case-first UX
- Renamed **Run on container** → **Run on this case**; header shows **Case ID** not Container.
- Collapsible **How to run on a case** help in the action bar.
- **get sidecar url** accepts `container_id`, `event_id`, `rule_name`, `investigation_id` and appends them to the sidecar URL automatically.

## [2.13.0] — 2026-07-26

### Readiness check + auto-fix
- **`playbook_readiness.py`** — validates code (actions, callbacks), integrations (asset preflight), container/run context, placeholder constants.
- Runs automatically on every draft preview; **`Readiness`** button and **`Apply auto-fixes`** in sidecar.
- API: `action=readiness_check` with optional `apply_fixes=1`.
- **`playbook_defaults_json`** asset field — auto-fill constants (e.g. `SLACK_CHANNEL`) and asset aliases for NL-generated playbooks.
- Slack added to asset resolver hints.

## [2.12.0] — 2026-07-26

### Organization templates via asset config
- **`custom_templates_json`** asset field — add org playbooks (`org-*` ids) without rebuilding the app.
- **`custom_templates.py`** — parse, validate Python, merge into catalog, scaffolds, and offline NL keywords.
- **`list_patterns`** returns `org_template_count`, `org_errors`, `org_warnings`; org templates show **[Org]** in UI.
- Destructive org templates inherit HITL import/run gates.

### UI / UX
- **Workflow strip** — Choose → Preview → Import → Run progress at top of sidecar.
- Template library shows shipped vs org counts; wizard collapsed by default.
- Clearer action bar on preview panel; chat labeled as optional custom build.

## [2.11.1] — 2026-07-26

### UI
- Removed redundant **Example prompts** pane; use **Guided wizard → Start** (offline) or **Use in chat** (NL when AI connected).
- Boot message points to wizard + template library only.

## [2.11.0] — 2026-07-26

### Investigation-aware sidecar + HITL
- **`investigation_context` API:** hydrates container artifacts from SOAR, suggests template from `rule_name` / ES notable context.
- Sidecar URL params: `container_id`, `event_id`, `rule_name`, `investigation_id` — forwarded on all API calls.
- **`run_playbook` API:** run imported playbook on linked container with audit logging; destructive templates require `destructive_confirm`.
- **Template tiers** in catalog (`safe` / `integration` / `destructive`); UI confirm gate before import/run of destructive templates.
- **Air-gap template manifest:** `scripts/build_template_manifest.py` → `dist/template-manifest.json`; handler `action=template_manifest`.
- Demo prep sidecar URLs include `event_id` and `rule_name` when available.

## [2.10.4] — 2026-07-26

### Customer-neutral naming
- Renamed template **`nnsa-failed-logins`** → **`failed-logins-okta`** (label: Excessive Failed Logins).
- Renamed playbook labels `nnsa_failed_logins` → `excessive_failed_logins`, `es_nnsa_response` → `es_notable_response`.
- Removed NNSA branding from docs, sidecar UI, wizard, and troubleshooting copy.
- Legacy pattern id `nnsa-failed-logins` still resolves via alias for existing imports/bookmarks.
- Docs: `NNSA_QUICK_START.md` → [FAILED_LOGINS_QUICK_START.md](docs/FAILED_LOGINS_QUICK_START.md).

## [2.10.3] — 2026-07-26

### VirusTotal template — close on malicious
- **`virustotal-enrichment` scaffold:** parses VT v3 `summary.malicious` / `last_analysis_stats.malicious`, adds verdict note, auto-closes container when detections ≥ `VT_MALICIOUS_THRESHOLD` (default 1).
- **Catalog copy** updated to match behavior; runtime fixture NL prompt aligned.

## [2.10.1] — 2026-07-26

### Template library expansion
- **11 templates** in categorized dropdown (left panel) — replaces small footer selector.
- **`pattern_catalog.py`** single source of truth; API `action=list_patterns`.
- **New scaffolds:** `panw-block-ip`, `virustotal-enrichment` (added to SCAFFOLDS, was NL-only stub).
- **`test_all_patterns.py`** — vets Python, COA, callbacks, assets, keyword routing for every template.

## [2.10.0] — 2026-07-26

### Offline-first expansion
- **Troubleshooting catalog:** `troubleshooting_catalog.py` maps errors to symptom/cause/fix/verify; attached to API error payloads.
- **Sidecar Troubleshooting guide:** searchable help panel + inline cards on errors (Copy steps).
- **Guided wizard:** Excessive Failed Logins, ES Notable, ServiceNow, ClearPass, Hello — no LLM required.
- **Pattern pack:** `failed-logins-okta` template; phishing-enrichment and insider-threat-ad scaffolds.
- **Okta fix:** `get user` passes collected `username`; clear/disable pass `user_id`.
- **Docs:** AIR_GAPPED_OPERATIONS.md, TROUBLESHOOTING.md, FAILED_LOGINS_QUICK_START.md.
- **Tests:** test_troubleshooting.py, test_local_nl_build.py.

## [2.9.6] — 2026-07-26

### Added

- **App branding:** Custom Playbook Builder logo (`logo.png` / `logo_dark.png`) for the SOAR Apps catalog and sidecar header.

## [2.9.5] — 2026-07-26

### Fixed

- **VPE invalid datapath / blank block editor:** Modern COA import no longer emits synthetic filter/collect/decision nodes with bogus datapaths. Action blocks bind to the real Python callback function (`lookup_okta_user`, etc.) so clicking a block opens the correct code.

## [2.9.4] — 2026-07-26

### Changed

- **No Splunk SOAR (phantom) app required:** Scaffolds use `phantom.add_note()` and `phantom.set_owner()` for notes and assignment instead of `phantom.act(..., assets=["soar"])`, so labs without a phantom connector asset import cleanly into the VPE.

## [2.9.3] — 2026-07-26

### Fixed

- **Missing Configuration (soar):** Built-in actions (`add note`, `assign`) now require a real **Splunk SOAR (phantom)** asset — not Playbook Builder / MCP bridge assets. COA nodes use connector **Splunk SOAR** with the mapped phantom asset name. Preflight blocks import with a clear message when no phantom asset exists.

## [2.9.2] — 2026-07-26

### Fixed

- **SOAR integration check:** Built-in SOAR actions (`add note`, `assign`) no longer offer Playbook Builder / “soar mcp bridge*” assets in the dropdown. When no real SOAR asset exists, preflight auto-resolves as **built-in SOAR** (no external asset).
- **`asset_defaults` loading:** Sidecar REST handler now reads custom settings from the asset `configuration` blob and from the asset name in the URL (`…/mcpbridge/chat`), so defaults like `{"okta": "okta"}` apply during preflight.

## [2.9.1] — 2026-07-26

### Fixed

- **HTTP 500 on Build:** SOAR now matches keyword templates (ServiceNow, Okta, etc.) **before** calling MCP, avoiding handler timeout while Ollama runs. MCP proxy timeout raised to 120s. Handler exceptions return JSON errors (HTTP 200) with traceback instead of opaque 500.
- **Okta offline path:** `okta-idp-response` template matches Okta NL prompts when MCP is slow or unavailable.

## [2.9.0] — 2026-07-26

### Added

- **Asset preflight:** Before import, Playbook Builder queries SOAR `/rest/asset`, maps scaffold keys (`servicenow`, `soar`, …) to configured asset names, and blocks import with a sidecar **Integration check** panel when integrations are missing or ambiguous.
- **`asset_defaults` asset setting:** JSON map on the Playbook Builder asset for lab-wide defaults (e.g. `{"servicenow": "snow_lab", "soar": "local"}`).
- **`preflight_import` API action** and COA `connectorConfigs` rewrite so modern imports avoid **Missing Configurations** when assets exist on SOAR.
- **Documentation:** [docs/ON_PREM_LLM.md](docs/ON_PREM_LLM.md) — private/on-prem LLM via OpenAI-compatible API (`OPENAI_BASE_URL`, Ollama/vLLM/LiteLLM examples, air-gapped checklist).

### Changed

- Import path rewrites `assets=[...]` in Python and COA action nodes to resolved configured names.
- Architecture, MCP integration, and handoff docs cross-link on-prem LLM guidance.

## [2.8.0] — 2026-07-26

### Added

- **Modern/visual imports:** Playbook Builder now packages embedded **COA** graphs (`coa.data.nodes/edges`) so imports open in the **Visual Editor** with blocks visible (not classic-only Python).
- **`coa_builder.py`:** Converts sidecar preview blocks into Splunk COA JSON alongside `{slug}.py`.

### Changed

- **Default import mode:** Modern COA + Python **3.13** metadata (no `phenv` auto-upgrade step — tool absent on SOAR 6.x labs).
- **Legacy 2.7 delete:** REST DELETE still unsupported (405); import continues with warning instead of hard failure.

## [2.7.27] — 2026-07-26

### Changed

- **Python 3.13:** App manifest and playbook import metadata now target **3.13** (fixes Apps UI “Python 3.9 deprecated” warning on SOAR 8.x).

### Fixed

- **REST playbook catalog:** Mac diagnose/migrate scripts now use `page_size=0` (and 0-based pagination) so SOAR 6.x returns all playbooks, not the default first 10.
- **Builder label match:** Detect `playbook_builder` labels even when SOAR appends suffix characters.
- **phenv discovery:** Detect when `playbooks_to_py3` is missing on SOAR 8.x; try direct script path and Python 3.13 interpreter; clearer errors pointing to re-import or UI migration.
- **Docs/scripts:** Verification uses `playbooks_to_py3 -h`, not `--help` (which triggers `exec: playbooks_to_py3: not found` when the tool is absent).

## [2.7.25] — 2026-07-26

### Fixed

- **phenv user:** Splunk requires `phenv` as user `phantom`. All invocations now use `sudo -u phantom /opt/phantom/bin/phenv ...` (fixes "This command must be run as user 'phantom'").

## [2.7.24] — 2026-07-26

### Fixed

- **MCP bridge SSH fallback:** When local phenv is blocked on SOAR, imports call `POST /agent/api/upgrade-python39` on the MCP bridge (Mac + SSH key → `sudo phenv` on SOAR). Requires MCP bridge running with `SOAR_HOST` / `SSH_KEY` env.
- **fix-environment-python39.sh:** Now uses SSH phenv + REST delete (reliable on SOAR 6.x) instead of in-app phenv only.

## [2.7.23] — 2026-07-26

### Fixed

- **phenv auto-upgrade:** Use Splunk default `_py3` suffix (not `_py39`), try `sudo -n phenv`, bundled `bin/phenv_upgrade.sh`, and broader converted-playbook discovery. Import step now shows the actual phenv error instead of a generic message.
- **Asset config:** `phenv_use_sudo` (default true) and optional `phenv_path` on the Playbook Builder asset.

## [2.7.22] — 2026-07-26

### Added

- **Automatic Python 3 upgrade:** Every import runs `ensure_playbook_python39()` — REST pin first, then `phenv playbooks_to_py3` on the SOAR host when still on 2.7 (SOAR 6.x).
- **Bulk environment fix:** `POST action=migrate_python39&confirm=1` upgrades all Python 2.7 playbooks in the local repo. Wrapper: `scripts/fix-environment-python39.sh --confirm`.

### Changed

- Python version check accepts any Python 3.x runtime (3.6 / 3.9 / 3.13 depending on SOAR release).

## [2.7.21] — 2026-07-26

### Fixed

- **SOAR 6.x Python 2.7:** Document and automate the correct path — `phenv playbooks_to_py3` on the SOAR host. REST re-import cannot change `python_version` on classic 2.7 playbooks (Option A alone will not work).
- **Migration safety:** `--delete-non-39` is now off by default (it could remove playbooks that REST cannot upgrade). Use `--phenv-ssh` instead.
- **Diagnostics:** `scripts/diagnose_playbook_python.py` lists every playbook's Python version and prints phenv commands.

## [2.7.20] — 2026-07-26

### Fixed

- **Python 2.7 stuck playbooks:** Classic SOAR cannot upgrade 2.7 playbooks in place. Imports now **delete** an existing 2.7 copy before re-importing with 3.9 metadata; flat `.py`-only fallback removed (it always created 2.7 classics).
- **Migration script:** Deletes legacy 2.7 playbooks before re-import, resolves new playbook id by slug, and supports `--slug servicenow_p1_incident` for targeted fixes.
- **SSH helper:** `scripts/convert_playbooks_py3_ssh.sh` runs `phenv playbooks_to_py3` on the SOAR host when REST migration is insufficient.

## [2.7.19] — 2026-07-26

### Changed

- **Python 3.9 pin:** All Playbook Builder imports set `python_version: "3.9"` in playbook `.json` metadata and attempt a post-import REST pin. Source is prefixed with `# pylint: disable=no-member` so SOAR validation accepts `phantom.collect2` / `phantom.act`.
- **Bulk migration script:** `scripts/migrate_playbooks_python39.py` re-imports builder-tagged playbooks on 3.9, dedupes slugs, and deletes builder copies still not on 3.9 (`--confirm` to apply).

## [2.7.18] — 2026-07-26

### Fixed

- **Sidecar Blocks preview:** Parse `phantom.act(action="…")` (ClearPass/ServiceNow templates) and order blocks by source position so Collect/Action steps appear after import.
- **Import messaging:** Post-import chat notes explain Python 3.13 update steps and why SOAR **Block results** stays empty for classic Python imports.

## [2.7.17] — 2026-07-26

### Fixed

- **Open in SOAR empty search:** Playbooks search now uses the SOAR repo slug (`hello_world`), not the display title (`Hello World`). Classic automation playbooks are indexed by filename slug.
- **Restore `slug_from_label`:** Missing helper could crash import with HTTP 500.

## [2.7.16] — 2026-07-26

### Fixed

- **Import resolve / Open in SOAR:** Trust `import_playbook` response id (e.g. 187) via GET `/rest/playbook/{id}` before catalog polling. Match SCM names like `hello_world/hello_world`.
- **Playbook naming:** Metadata uses display title (**Hello World**). Tarball is root-level `hello_world.py` + `hello_world.json` (no nested `hello_world/hello_world` folder). **Open in SOAR** searches by display name.

## [2.7.15] — 2026-07-26

### Fixed

- **Import HTTP 500 / stuck on Uploading:** Resolve phase no longer hammers SOAR with dozens of loopback REST calls (was exceeding handler timeout). Single catalog fetch per poll (8×, 2s apart). JsonResponse-safe playbook records. Import tries flat then folder tarball once, resolves once.

## [2.7.14] — 2026-07-26

### Fixed

- **Import not registering in Playbooks (SOAR 6.5):** Removed post-import **SCM pull** — it could overwrite a fresh local import. Import now matches MCP (`scm_id` + `force` only), tries **flat `.py` tarball first**, polls up to 15s with paginated/filtered `GET /rest/playbook`, and logs REST diagnostics in `import_attempts`.

## [2.7.13] — 2026-07-26

### Fixed

- **Open in SOAR → `/playbook/{id}` 404 on SOAR 6.5:** Button now always opens **Playbooks search** (`/playbooks?search=hello_world`), never the VPE/Python deep link. Sidecar computes the search URL client-side so older cached bundles cannot fall back to `/playbook/183?editor=python`.
- **Import ID verification:** Playbook must appear in `GET /rest/playbook` catalog (same index the UI searches), not only `GET /rest/playbook/{id}`. Normalizes SCM path names like `hello_world/hello_world`.

## [2.7.12] — 2026-07-26

### Fixed

- **False-positive import success:** Reject `import_playbook` responses with `failed: true` / error payloads. Metadata `name` now matches tarball folder slug (`hello_world`, not display title). Packaging uses `gzip(tar)` like MCP SOAR; flat `.py`-only tarball retry for classic SOAR 6.x.
- **Playbook ID verification:** Only accept IDs when `GET /rest/playbook/{id}` name matches the imported slug/display name (poll up to 10s).
- **Open in SOAR:** Primary link opens **Playbooks** search (`/playbooks?search=…`) so classic Python playbooks on SOAR 6.5 appear even when `/playbook/{id}` 404s.

## [2.7.11] — 2026-07-26

### Fixed

- **Open in SOAR / "Given Playbook does not exist":** After import, resolve playbook ID by polling `/rest/playbook` and verifying `GET /rest/playbook/{id}` (no stale/wrong IDs). **Open in SOAR** now uses `?editor=python` for classic Python imports instead of the Visual Editor route that 404s on unconverted playbooks.

## [2.7.10] — 2026-07-26

### Fixed

- **Import loopback 404 (`/rest/rest/...`):** `get_rest_base_url()` already includes `/rest`; URL builder no longer duplicates the prefix. Retries on HTTP 404 / `not found rest`.

## [2.7.9] — 2026-07-26

### Fixed

- **Import loopback 401 (session token):** Retry loopback with client-matching `Host` (preserves browser session), platform `get_rest_base_url()`, and `ph-auth-token` from headers/cookies. Retries on HTTP 401 / missing session token instead of stopping after the first loopback Host spoof.

### Added

- Optional asset field **`soar_rest_token`** — paste a SOAR REST API `ph-auth-token` when browser session forwarding is insufficient for `import_playbook`.

## [2.7.8] — 2026-07-26

### Fixed

- **Sidecar POST 401:** Import/chat POSTs now send Django CSRF (`X-CSRFToken` from `csrftoken` cookie) and `X-Requested-With: XMLHttpRequest`. SOAR often allows GET without CSRF but rejects POST with **401 Unauthorized**.

## [2.7.7] — 2026-07-26

### Fixed

- **Import loopback (lab appliances):** Connect to the client-facing SOAR IP while sending an allowed `Host` header (`127.0.0.1` / `localhost`). Retries alternate targets when Django rejects the host or TCP fails on loopback-only binds. `import_attempts` now includes per-URL loopback diagnostics.

## [2.7.6] — 2026-07-26

### Fixed

- **Import loopback on lab SOAR:** Internal REST calls use `127.0.0.1` with a matching `Host` header so Django does not reject external IPs missing from `ALLOWED_HOSTS`.

### Changed

- App description updated to capability-focused copy (no vendor-specific scaffold names).

## [2.7.5] — 2026-07-26

### Fixed

- **Import from sidecar / REST handler:** SOAR REST handlers cannot use `phantom.app.rest`. Import now loops back to `/rest/import_playbook` via HTTP using the caller's session cookies or `Authorization` header (Splunk-documented REST handler pattern).

## [2.7.4] — 2026-07-26

### Fixed

- **Import on SOAR 8.5:** `draft_import` no longer calls `phantom.app.build_phantom_rest_url` (missing on many builds). New `soar_rest.py` tries `phantom.rules`, `get_rest_base_url`, then `/rest/...` fallback.

## [2.7.3] — 2026-07-26

### Changed

- **Package rename:** `phantom_playbook_builder` → `soar_playbook_builder` (install artifact: `dist/soar_playbook_builder.tgz`)
- E2E and helper scripts accept both package names during migration from older installs

## [2.7.2] — 2026-07-24

### Added

- Production E2E validation: `scripts/e2e_validate.py`, `scripts/run-e2e-validate.sh`, `docs/E2E_VALIDATION.md`
- HTML/Markdown/JSON reports with quick-verify URLs (`dist/e2e/`)
- MCP integration guide (`docs/MCP_INTEGRATION.md`)
- GitHub Actions workflow to build `.tgz` on release tags

### Changed

- Neutral default `ai_instructions` and `publisher` (no environment-specific branding)
- Sidecar product title: **Playbook Builder**
- Customer docs reframed as Mode A (localized) vs Mode B (MCP bridge + optional LLM)

### Removed

- Lab-specific demo walkthrough from app documentation package

## [2.7.0] — 2026-07-22

### Added

- React sidecar UI with block preview, import progress, and bridge status pill
- Draft import timeouts and UI recovery for long `import_playbook` operations

### Changed

- Import pipeline step logging in sidecar

## [2.6.0] — 2026-07-18

### Added

- Visual preview tabs (blocks, diagram, storyboard, code) via `preview_visual.py`
- Local NL fallback when MCP bridge is unreachable

## [2.5.0] — 2026-07-10

### Added

- `mcp_bridge_url` asset setting for optional Mode B
- `test connectivity` and `get sidecar url` actions

---

[2.7.2]: https://github.com/your-org/soar-playbook-builder/releases/tag/v2.7.2
