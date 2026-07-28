# SOAR Playbook Builder

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](soar_playbook_builder/soar_playbook_builder.json)
[![Splunk SOAR 8.5+](https://img.shields.io/badge/SOAR-8.5%2B-65A637)](docs/PLAYBOOK_BUILDER_GUIDE.md)
[![Version](https://img.shields.io/badge/version-2.27.0-informational)](CHANGELOG.md)

**Describe Splunk SOAR playbooks in plain language, review a
capability-grounded plan, and deterministically preview visual and Python
artifacts before import.**

**Engineering alpha Splunk SOAR custom app.** It is suitable for isolated lab
evaluation and offline development but is not yet production-certified. The
trusted path currently stops at **Review**. Import and Run remain locked or
lab-only until the live authorization, multi-user isolation, native Visual
Playbook Editor (VPE), and supported-version gates in the
[trusted release plan](docs/TRUSTED_RELEASE_PLAN.md) pass. Every install
includes sample cases (9001–9005), and the mock-friendly development mode can
exercise the UI without a SOAR instance.

The new declarative IR/compiler path is deliberately **review-only**:
`import_enabled=false` until live SOAR authorization, native-VPE, idempotency,
and runtime gates pass. The existing Python scaffold/import flow remains
available for isolated legacy lab evaluation but is not represented as trusted.

**Repository:** [github.com/LeiterConsulting/soar-playbook-builder](https://github.com/LeiterConsulting/soar-playbook-builder)

**Upstream:** [github.com/wts408/soar-playbook-builder](https://github.com/wts408/soar-playbook-builder)

---

## Current milestone: offline trusted foundation

[Pull request #1 — Add offline trusted foundation and release
gates](https://github.com/LeiterConsulting/soar-playbook-builder/pull/1) merged
the `codex/gate0-foundation` milestone into `main`. It established the largest
safe boundary we can verify without a live Splunk SOAR instance and remains the
change record for reviewing that foundation.

### What is implemented and proven offline

| Area | Current result | Trust status |
|------|----------------|--------------|
| Playbook representation | Closed, versioned IR 1.0 with schema, grammar, bounded values, typed graph validation, and canonical hashing | Trusted for offline review |
| Compilation | Deterministic sibling Python and visual-preview artifacts with matching IR hashes and node inventories | Trusted for preview; native VPE import compatibility is not yet claimed |
| Preflight | Capability-grounded checks return a closed, structured `GapReport` for actions, assets, parameters, datapaths, permissions, objects, egress, graph shape, and evidence age | Trusted against the evidence supplied to it |
| Model boundary | Local/OpenAI-compatible provider contract, constrained-output probing, strict decoding, and bounded repair | Provider boundary tested; a real local model is not yet qualified |
| Retrieval and templates | Network-free BM25 baseline, 11 strict-IR templates, and bounded capability context | Offline baseline complete; domain review and corpus expansion remain |
| Review API and UI | Clean and blocked reviews expose canonical IR, exact gaps, provenance, and artifact hashes | Review-only; Import and Run remain locked |
| Security and resilience | Bounded requests/responses, SSRF and redirect controls, browser security headers, atomic capability-index recovery, secret/SAST/dependency gates, and deterministic package inspection | Repository boundary tested; live platform controls still require evidence |
| Release engineering | SHA-pinned CI, reproducible archive, license inventory, checksums, and CycloneDX UI SBOM | Offline build gate complete; signing policy remains open |

The recorded verification snapshot is **275 Python tests**, **7 evaluation
suites**, **40/40 exact no-model cases**, **11/11 dual-compiled templates**,
**1.000 top-5 retrieval recall** on the fixed corpus, **7 UI tests**, and **4
Chromium tests**, plus clean dependency, SAST, documentation, package, and
reproducibility gates. These are bounded repository results, not evidence of
live SOAR behavior.

Start with these records:

- [Implementation record](docs/OFFLINE_FOUNDATION_IMPLEMENTATION.md) — what
  changed, why it changed, test evidence, and legacy containment.
- [Offline readiness and live handoff](docs/OFFLINE_READINESS.md) — exact
  success criteria, commands, and claims that remain deferred.
- [Threat model](docs/THREAT_MODEL.md) — assets, trust boundaries, controls,
  residual risks, and live evidence requirements.
- [Trusted release plan](docs/TRUSTED_RELEASE_PLAN.md) — ordered delivery gates
  and production acceptance criteria.
- [Trusted review contract](docs/TRUSTED_REVIEW.md) — the permanent review/import
  separation until live authorization is implemented.

### Important technology decisions for review

- **Strict IR replaces executable model or organization-authored Python** in the
  trusted path. Python and visual previews are deterministic compiler outputs.
- **React + TypeScript remain** for the sidecar, while React Router was removed
  in favor of a small typed hash router to reduce dependency and advisory
  surface.
- **Vite 6.4 is retained temporarily** because it receives security backports;
  a Vite 8 migration should be evaluated as an isolated compatibility change.
- **Node.js 24 LTS is the build baseline.** The packaged SOAR runtime remains
  Python 3.13 and avoids unnecessary third-party runtime dependencies.
- The privileged **SOAR 6/Python 2 migration path was removed** from the SOAR
  8.5+ package rather than carrying an unsafe automatic overwrite/delete path.
- Legacy Python templates and scaffold/import behavior are explicitly
  **untrusted lab compatibility**, not part of the trusted design.

The rationale and alternatives are recorded in
[the implementation record](docs/OFFLINE_FOUNDATION_IMPLEMENTATION.md#5-legacy-containment-and-technology-changes)
and [trusted release plan](docs/TRUSTED_RELEASE_PLAN.md#5-technology-decision-register).

### How to review this milestone

No live SOAR instance is required for the first four review passes:

1. Review the merged scope and security boundary in
   [PR #1](https://github.com/LeiterConsulting/soar-playbook-builder/pull/1),
   then confirm that no offline result is presented as live authorization.
2. Review the [IR](docs/IR_CONTRACT.md),
   [compiler](docs/COMPILER_CONTRACT.md),
   [GapReport](docs/GAP_REPORT_CONTRACT.md),
   [model](docs/MODEL_BOUNDARY.md), and
   [retrieval](docs/RETRIEVAL_CONTRACT.md) contracts before reviewing their
   implementations.
3. Reproduce the offline gates:

   ```bash
   python3 -m pytest -q tests
   python3 soar_playbook_builder/eval/harness.py --suite all
   python3 scripts/check_docs.py

   cd sidecar-ui
   npm ci
   npm audit --audit-level=high
   npm test
   npx --no-install playwright install chromium
   npm run test:e2e
   npm run build

   cd ../validation-console
   npm ci
   npm audit --audit-level=high
   npm run build

   cd ..
   ./package_app.sh
   python3 scripts/inspect_app_archive.py dist/soar_playbook_builder.tgz
   ```

4. Run the mock UI, inspect clean and blocked trusted reviews, and verify that
   Import and Run cannot become enabled:

   ```bash
   cd sidecar-ui
   npm run dev
   # open http://localhost:5173
   ```

5. Record design disagreements, missing tests, threat-model gaps, or technology
   changes as focused PR comments or GitHub issues. Keep live-SOAR findings
   separate from repository-only findings so the evidence boundary stays clear.

### Next development gates

| Priority | Gate | Success criteria before advancing |
|----------|------|-----------------------------------|
| 1 | Post-merge foundation review | `main` CI is green; contracts, threat model, technology choices, and lab-only labels are reviewed; follow-up findings have owners and acceptance criteria; no unresolved reachable critical/high dependency or high-confidence security finding |
| 2 | Live SOAR discovery | Sanitize and record authenticated principal/role, session/origin/CSRF, proxy, REST, capability-harvest, restart, and supported-version behavior on a non-production instance |
| 3 | Native VPE qualification | Hello and representative branching artifacts round-trip through the supported Visual Playbook Editor without semantic or hash-bound inventory drift |
| 4 | Trusted mutation design | Actor-bound approval, role authorization, commit-time hash revalidation, durable idempotency, per-user isolation, and protected audit evidence pass negative and multi-user tests |
| 5 | Safe live execution | Strict templates import and run only on disposable cases with expected-output, timeout, retry, cleanup, restart, and rollback assertions |
| 6 | Accuracy and model qualification | Corpus expands to at least 100 domain-reviewed cases; a named weakest supported local model passes constrained-output, repair, hallucination, latency, and offline-network gates |
| 7 | Release candidate | Supported SOAR/browser matrix, clean install/upgrade/rollback, manual keyboard/screen-reader and analyst review, current SBOM/audits, and selected signing/provenance policy all pass |

The live work must follow the evidence order in
[OFFLINE_READINESS.md](docs/OFFLINE_READINESS.md#handoff-to-the-other-machine);
trusted Import must not be enabled merely because an offline `GapReport` is
clean.

---

## At a glance

![Playbook Builder sidecar — chat, template scaffolds, block preview, and Import to SOAR](docs/assets/builder-overview.svg)

*Replace with a live screenshot after install: SOAR → your asset → **Open sidecar** → capture Build tab.*

---

## Prerequisites

### On your build machine (packaging the `.tgz`)

| Requirement | Notes |
|-------------|--------|
| **bash**, **tar**, **git** | macOS or Linux (RHEL/Ubuntu both work) |
| **Node.js 24 LTS** and **npm** | Builds the React sidecar (`sidecar-ui/`); Node 20 is end-of-life |
| **Python 3.9+** | Utility scripts and optional E2E validation |

Optional (E2E / validation only):

```bash
pip install -r requirements.txt   # httpx for scripts/e2e_validate.py
```

### On Splunk SOAR (runtime)

| Requirement | Notes |
|-------------|--------|
| **Splunk SOAR 8.5+** | See `min_phantom_version` in app manifest |
| **Python 3.13** | SOAR platform Python for imported playbooks |
| **RHEL-compatible OS** | Standard SOAR appliance or self-managed host |
| **Asset + permissions** | Analyst role with playbook edit/import |

**Mode A (default):** templates, scaffolds, validate, import — **no MCP or API keys required.**

**Mode B (optional):** natural-language chat via an external MCP agent bridge — see [Configuration](#configuration) and [docs/MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md).

---

## Quick start

Three commands to build the installable app:

```bash
git clone https://github.com/LeiterConsulting/soar-playbook-builder.git
cd soar-playbook-builder
./package_app.sh
```

Install on SOAR:

1. **SOAR → Apps → Install App** → select `dist/soar_playbook_builder.tgz`
2. **Configure → Asset Configuration** → create an asset (e.g. `playbook_builder`)
3. Run action **Test connectivity** (Mode B) or open the sidecar URL:

```bash
SOAR_URL=https://your-soar:8443 SOAR_USER=admin SOAR_PASS='***' ASSET=playbook_builder \
  ./scripts/print_sidecar_url.sh
```

**Try it without SOAR** (mock UI):

```bash
cd sidecar-ui && npm ci && npm run dev
# → http://localhost:5173  (#/build · #/run · #/help)
```

To make the mock UI reachable from another trusted machine on the same LAN, use
`npm run dev:lan`, then open `http://<developer-machine-ip>:5173`. This opt-in
command listens on all interfaces; keep the host firewall enabled and do not
expose port 5173 to the internet. An installed SOAR app is served by SOAR's
HTTPS endpoint and does not open a separate listener.

---

## Configuration

Copy the template and fill in values for your environment:

| File | Purpose |
|------|---------|
| [**config.example.yaml**](config.example.yaml) | SOAR asset fields (`mcp_bridge_url`, `asset_defaults`, etc.) |
| [scripts/env.e2e.example](scripts/env.e2e.example) | E2E validation against a live SOAR |
| [sidecar-ui/.env.example](sidecar-ui/.env.example) | Local Vite dev against live SOAR |

**Minimal Mode A asset:** leave `mcp_bridge_url` empty; set `ai_instructions` if desired; map integrations in `asset_defaults` (JSON string in SOAR UI).

**Mode B:** set `mcp_bridge_url` to your HTTPS bridge (e.g. `https://bridge.internal:8003/agent`). LLM keys live on the **bridge host**, not in this repo. Plain HTTP requires the explicit lab-only asset override.

Full setup: [docs/PLAYBOOK_BUILDER_GUIDE.md](docs/PLAYBOOK_BUILDER_GUIDE.md)

---

## Deployment modes

| Mode | Bridge | Best for |
|------|--------|----------|
| **A — Localized** | None | Air-gapped, templates, validate, import |
| **B — Bridge + LLM** | MCP host | Open-ended NL chat — [ON_PREM_LLM.md](docs/ON_PREM_LLM.md) |

Sidecar base URL: `https://<soar>/rest/handler/<directory>/<asset>/`

---

## Documentation

| Guide | Contents |
|-------|----------|
| [SECURITY.md](SECURITY.md) | Release status, private vulnerability reporting, and security expectations |
| [OFFLINE_FOUNDATION_IMPLEMENTATION.md](docs/OFFLINE_FOUNDATION_IMPLEMENTATION.md) | Consolidated implementation, security, testing, technology, and live-handoff record for v2.27.0 |
| [OFFLINE_READINESS.md](docs/OFFLINE_READINESS.md) | What is proven now, exact success criteria, and the live-instance handoff |
| [THREAT_MODEL.md](docs/THREAT_MODEL.md) | Trust boundaries, threats, implemented controls, and residual live evidence |
| [TRUSTED_RELEASE_PLAN.md](docs/TRUSTED_RELEASE_PLAN.md) | Current assessment, technology decisions, delivery gates, tests, and release criteria |
| [IR_CONTRACT.md](docs/IR_CONTRACT.md) | Versioned non-executable graph, bindings, schema, grammar, and validation boundary |
| [COMPILER_CONTRACT.md](docs/COMPILER_CONTRACT.md) | Deterministic Python/visual artifacts, round-trip guarantees, and live-SOAR qualification boundary |
| [GAP_REPORT_CONTRACT.md](docs/GAP_REPORT_CONTRACT.md) | Fail-closed action, asset, parameter, datapath, permission, egress, object, graph, and staleness policy |
| [NO_MODEL_EVAL.md](docs/NO_MODEL_EVAL.md) | 40-case offline IR → compiler → GapReport corpus and exact pass criteria |
| [MODEL_BOUNDARY.md](docs/MODEL_BOUNDARY.md) | Hardened provider, strict IR decode, bounded repair, and offline adversarial gate |
| [RETRIEVAL_CONTRACT.md](docs/RETRIEVAL_CONTRACT.md) | Network-free BM25, bounded capability context, and 11 canonical IR templates |
| [TRUSTED_REVIEW.md](docs/TRUSTED_REVIEW.md) | Review-only REST/UI path with preflight and artifact provenance; import remains locked |
| [ON_PREM_LLM.md](docs/ON_PREM_LLM.md) | Private model deployment policy and qualification criteria |
| [PLAYBOOK_BUILDER_GUIDE.md](docs/PLAYBOOK_BUILDER_GUIDE.md) | Install, configure, operate, troubleshoot |
| [FAILED_LOGINS_QUICK_START.md](docs/FAILED_LOGINS_QUICK_START.md) | Failed Logins → Okta in ~15 minutes |
| [RUN_TAB_DEMO.md](docs/RUN_TAB_DEMO.md) | Sample cases 9001–9005 smoke test |
| [FRESH_INSTALL_AND_MIGRATION.md](docs/FRESH_INSTALL_AND_MIGRATION.md) | Redeploy to a new SOAR (~15 min) |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Mode A vs B, components |
| [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) | Mode B HTTP flow |
| [AIR_GAPPED_OPERATIONS.md](docs/AIR_GAPPED_OPERATIONS.md) | Offline — no LLM/MCP |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptom index |
| [GITHUB_PUBLISHING.md](docs/GITHUB_PUBLISHING.md) | Releases and tags |

More guides: [docs/](docs/) · [CHANGELOG.md](CHANGELOG.md)

---

## REST routes

| Route | Description |
|-------|-------------|
| `chat` | Sidecar UI + builder API |
| `widget` | VPE poll widget |
| `poll_playbook` | Playbook change fingerprint |
| `proxy_chat` | MCP proxy (Mode B) |

---

## Releases

```bash
./package_app.sh
APP_VERSION="$(python3 -c 'import json; print(json.load(open("soar_playbook_builder/soar_playbook_builder.json"))["app_version"])')"
git tag "v${APP_VERSION}"
git push origin "v${APP_VERSION}"
```

GitHub Actions attaches the `.tgz`, UI CycloneDX SBOM, and `SHA256SUMS` to the
Release. The tag must match the manifest version. Pre-tag validation:
[docs/E2E_VALIDATION.md](docs/E2E_VALIDATION.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — fork, branch, run tests, open a PR.

---

## License

[MIT License](LICENSE) — customize `publisher` and branding before internal distribution. Not a Splunk product; see [ATTRIBUTION.md](ATTRIBUTION.md).
