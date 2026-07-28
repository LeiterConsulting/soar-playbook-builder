# SOAR Playbook Builder — Trusted Release Plan

- **Assessment date:** 2026-07-28
- **Assessed revision:** `13486a6` (`main`)
- **Planning authority:** [`AIR_GAP_BUILD_SPEC.md`](AIR_GAP_BUILD_SPEC.md) and [`AGENTS.md`](../AGENTS.md)

This document turns the existing product documentation and implementation into an ordered release plan. It is intentionally stricter than the current README: the repository is a promising engineering alpha, not yet a production-trustworthy security product.

## 1. Executive assessment

The application already demonstrates a coherent user journey:

1. choose a built-in or organization template,
2. preview generated Python and a block-flow representation,
3. check assets and readiness,
4. import to Splunk SOAR,
5. run on a case with confirmation,
6. use optional coach, tutor, ES-link, and MCP-bridge flows.

The implementation is strongest as an offline template/scaffold builder. Strict
IR, deterministic dual-artifact compilation, capability-grounded preflight, a
40-case no-model corpus, and a constrained provider/decoder with bounded repair
now pass offline gates. The strict path is connected to the installed app as a
review-only API/UI surface, including strict organization IR, but cannot feed
Import or Run. It has not been qualified against a real local model or live
SOAR. It is therefore not yet safe to represent the product as a general
natural-language playbook compiler. The legacy Mode B bridge can still return
Python, which remains outside the trusted path.

### Current release classification

| Area | Classification | Why |
|---|---|---|
| Mode A: templates, preview, readiness | Engineering alpha | Useful and well tested locally, but security and live-SOAR gates remain |
| Import and run | Lab-only | Mutates SOAR and needs authorization, isolation, and live-runtime evidence |
| Coach and tutor | Prototype | UI works; content accuracy and usability are not yet evaluated |
| Mode B: bridge/LLM | Experimental; must be disabled by default | Bypasses the required IR/compiler trust boundary |
| Air-gapped operation | Partial | IR/compilation are offline and deterministic, and the mock browser gate rejects external requests; installed-runtime capture and complete provenance remain |
| Production release | Not ready | Live authorization, native-schema/import/runtime qualification, and platform certification remain incomplete |

### Verified local baseline

| Check | Result |
|---|---|
| Repository | Cloned and tracking `origin/main` |
| Python tests | `275 passed` |
| Python compilation | Passed |
| Capability eval suite | Passed |
| Sidecar component/navigation tests | 7 passed, including targeted structural axe scans |
| Chromium browser tests | 4 passed: routes, trust lock, full axe scan, three widths, console/errors, and zero external requests |
| Sidecar TypeScript/Vite build | Passed |
| Validation-console TypeScript/Vite build | Passed |
| App packaging | Byte-reproducible archive passes traversal/link/size/mode/license/manifest inspection |
| Python dependency advisory scan | No known advisory in the pinned `httpx` dependency at assessment time |
| Validation-console npm audit | 0 vulnerabilities |
| Sidecar npm audit | 0 vulnerabilities after removing React Router |
| Bandit | 0 high and 0 medium findings in app + scripts gate |
| Full-history credential scan | `gitleaks` found no leaks in repository history |
| Live mock UI | Build, Run, Help, and Coach routes load without console/page errors or external requests |

Passing local tests proves the current implementation is internally consistent. It does not prove authorization, SOAR compatibility, multi-user isolation, generated-playbook correctness, or production resilience.

### Gate 0 foundation branch progress

The `codex/gate0-foundation` branch substantially addresses SEC-002, SEC-003,
SEC-006, SEC-007, SEC-009, and SEC-010 by removing shared draft state, escaping
HTML bootstrap values, redacting internal diagnostics, making mutations POST-only,
removing external fonts, and replacing React Router with typed native hash routing.
Every response from the app handler now receives no-store, MIME-sniffing,
referrer, framing, permissions, cross-origin resource, and CSP controls; inline
scripts were removed from both HTML shells.
SEC-004 is partially addressed: optional bridge HTTPS now verifies certificates,
plain HTTP requires an explicit lab override, and redirects and unsafe target
classes are rejected; the SOAR loopback REST adapter now verifies by default and
supports an explicit CA bundle plus a lab-only override, pending live-platform
certificate testing. SEC-005 and SEC-012 are partially addressed through central
bridge URL validation and bounded bridge/handler bodies. SEC-008 is substantially
addressed by using a password field and permanently excluding secrets from
configuration import/export. SEC-011 is partially addressed with PR CI,
dependency audits, packaging checks, Dependabot, and a private-disclosure
policy; full-history secret scanning and web dependency SBOM generation are now
gated, while app-level SBOM/provenance remains.
REL-001 is substantially addressed with locked atomic replacement, SHA-256
integrity metadata, last-known-good recovery, and corruption/interrupted-write
tests. SEC-001 now has a default-admin action classification and privacy-safe
audit record, but authorization remains deliberately audit-only until a live
SOAR request proves a platform-authenticated principal and role signal. Caller
role headers are never trusted.
Standing-spec step 2 now has an offline implementation: versioned typed IR,
closed JSON Schema, schema-derived GBNF, canonical serialization/hash, bounded
JSON literals, allowlisted helper nodes, and deterministic DAG/prior-output
validation. Standing-spec step 3 now has an offline compiler with structured
datapaths, explicit callbacks, run-scoped results, fail-closed unbound assets,
byte-stable Python/visual JSON, embedded provenance, golden hashes, artifact
parity, tamper rejection, and lossless round-trip tests. The visual artifact
explicitly reports native schema compatibility as unverified. Neither IR nor the
new compiler is connected to import or execution until preflight, migration,
review, and live-SOAR qualification gates pass.
Standing-spec step 4 also has an offline implementation: a closed GapReport,
explicit evaluation time, exact action/asset/parameter/datapath checks,
fail-closed permission and object evidence, operating-mode egress policy,
non-automatic offline substitutions, index version/age checks, static
remediation, independent schema validation, and a clean synthetic
false-positive control. Live permission, object, asset-health, and native-output
evidence remains unavailable and therefore blocked.
Standing-spec step 5 now has 40 fixed no-model cases. Every case validates as
IR, compiles to both artifacts, round-trips, and matches its exact expected
report status/gap set. The corpus seeds all deterministic preflight gap IDs and
passes with network socket creation denied.
Standing-spec step 6 now has an offline implementation: a narrow standard
library OpenAI-compatible provider, strict endpoint/address/TLS/size policy,
constraint capability probe, duplicate-key-safe JSON decode, authoritative
provenance stamping, IR-only output, bounded structured repair, sanitized
terminal generation gaps, and scripted adversarial coverage. Real
model/runtime qualification and trusted REST/UI integration remain pending.
Standing-spec step 7 now has an offline implementation: deterministic BM25 over
local action metadata and canonical IR templates, hard action/template/asset
context limits, 11 shipped IR exemplars with dual-compiler round trips, optional
reciprocal-rank fusion without a shipped embedding dependency, and a fixed
20-intent lexical corpus with 1.000 top-5 action recall. The suite passes with
socket creation denied.
The strict pipeline is now exposed through review-only REST actions and a
separate UI trust card. It returns canonical IR, exact GapReport, compiler
version, review/artifact hashes, and native-schema qualification status while
hard-coding trusted Import off. The legacy Python draft path is not treated as
trusted and cannot consume the review payload accidentally.
These items are not considered closed until the branch is reviewed and the
applicable live-SOAR tests pass.

## 2. Product promise and supported scope

### Release north star

An analyst can describe or select a workflow, receive a deterministic plan grounded only in the capabilities of their local SOAR instance, review every gap and side effect, and import an accurate playbook without required network egress or unreviewed model-written code.

### Functional user journeys

A release is “functional” only when all applicable journeys pass in a supported SOAR environment:

| Journey | Required outcome |
|---|---|
| First install | Admin installs the `.tgz`, creates an asset, runs self-test, and receives precise remediation for every failed prerequisite |
| Offline template build | Analyst selects a template and gets byte-stable IR, Python, visual JSON, readiness, and a gap report with the network disabled |
| Natural-language build | Supported local model produces schema-valid IR; invalid output is repaired or returns a structured blocked report |
| Capability grounding | Every app, action, parameter, output, asset, and egress claim traces to the current capability index |
| Review | Analyst sees the proposed IR, material changes, missing assets, egress, destructive actions, and compiled diff before import |
| Import | Authorized user imports once; retry is idempotent and cannot import another user's draft |
| Run | Authorized user runs against the intended container only after the correct confirmation level |
| Failure recovery | Timeouts, bridge loss, stale index, bad model output, and SOAR errors return stable error codes and safe recovery steps |
| Upgrade/migration | Config migrates with secrets redacted, generated content remains compatible, and rollback is documented and tested |

### Initial support boundary

- Splunk SOAR 8.5.x and Python 3.13 are the first certification target.
- Mode A ships before Mode B.
- Air-gapped and restricted modes are release targets, not optional variants.
- The minimum supported viewport should be explicit. The recommended target is 1200 CSS pixels and above, matching Splunk's own playbook-editor guidance; 1024 pixels must either become usable or show a clear unsupported-width message.
- Unsupported apps/actions must produce a `GapReport`, not a guessed scaffold.

## 3. Current capability map

| Capability | Current state | Release work |
|---|---|---|
| Built-in templates | 11 patterns with tiers and confirmations | Convert canonical templates to IR and add expected-artifact fixtures |
| Organization templates | Strict, bounded IR config is the default; legacy Python is ignored unless explicitly enabled | Provide inventory/migration tooling and keep legacy compatibility disabled |
| Local NL matching | Keyword-driven template selection | Retain as deterministic fallback; measure intent precision |
| Python preview | Legacy scaffold remains in product flow; deterministic IR compiler exists offline | Route reviewed IR through the compiler only; keep highlighting boundary tested |
| Visual preview | Legacy heuristic remains in product flow; direct IR renderer exists offline | Replace product flow after live native-schema qualification |
| Readiness/preflight | Legacy heuristics remain in product flow; deterministic IR/index GapReport exists offline | Route reviewed IR through the new validator and surface structured evidence |
| Capability index | Apps/actions/assets/vocab baseline and persistence | Complete roles, permissions, lists, playbooks, live CEF, atomic persistence, scheduling, and staleness behavior |
| Import/sync | Implemented with confirmation and several fallbacks | Make POST-only, authorized, idempotent, isolated, size-limited, and audited |
| Run on case | Confirmation and destructive confirmation exist | Enforce role/container scope, replay protection, audit, and live tests |
| Coach/tutor | Functional mock UI and local suggestions | Define evidence rules, accuracy evals, and role-specific usability tests |
| MCP bridge | Health, proxy, draft, and chat paths | Authenticate, validate URL/TLS, constrain requests, return IR only |
| IR | Offline gate implemented | Convert templates, integrate only behind preflight/review, and qualify migrations |
| Deterministic compiler | Offline gate implemented | Qualify native JSON, callbacks, joins, prompts, and import on SOAR 8.5.x |
| Structured validator | Offline gate implemented | Integrate behind review/import and populate live permission/object evidence |
| Eval corpus | 40-case no-model gate covers all deterministic gap IDs | Add manually reviewed template IR and at least 100 full weakest-model fixtures |
| Offline package | Reproducible inspected archive bundles local data, docs, license, attribution, and dependency notices | Add signed provenance and clean-install evidence |
| Release automation | SHA-pinned Actions, PR audits, secret scan, SBOM, checksum, tag/version, and package gates added | Add provenance signing, clean-install verification, and rollback evidence |

## 4. Release-blocking findings

These findings are planning inputs, not claims that an exploit has been demonstrated.

### P0 — must be resolved before pilot use

| ID | Finding | Required outcome |
|---|---|---|
| SEC-001 | REST handlers do not receive normal Django `user` or `session` state, while the handler exposes read and mutating operations | Define and test an explicit authentication/authorization policy for each route and action; deny by default |
| SEC-002 | Drafts use a process-global cache whose default key is the shared string `builder` | Remove shared mutable draft state. Until IR lands, require an unguessable, expiring draft ID scoped to authenticated request context; target design sends only IR to a stateless compiler/import path |
| SEC-003 | `_render_template` performs raw string substitution into HTML attributes | Serve a static shell and load validated bootstrap JSON, or apply context-correct escaping; add stored/reflected XSS tests |
| SEC-004 | Bridge and loopback REST clients set `check_hostname = False` and `CERT_NONE` | Verify TLS by default; support an explicit CA bundle; permit insecure transport only in a visibly unsafe lab mode that cannot be selected accidentally |
| SEC-005 | Configured bridge URLs are used without a strict scheme/host/port policy | Add URL parsing, `https` policy, loopback/link-local/metadata protections, DNS/IP validation, allowlists, redirect restrictions, and SSRF tests |
| SEC-006 | Error responses can include the last 800 characters of a Python traceback | Return stable public error codes and correlation IDs; keep stack traces in protected logs only |
| SEC-007 | Mutating chat actions can be selected through GET query parameters | GET is read-only. Move every mutation to POST, enforce content type, CSRF/origin policy where applicable, confirmation, authorization, and replay/idempotency controls |
| SEC-008 | `soar_rest_token` is declared as a normal string and can be exported when a request flag is set | Mark it as a password/secret, never return it through the UI, restrict secret export to a separately authorized admin workflow, and audit all access |
| SEC-009 | Google Fonts are loaded from public origins in the development and packaged sidecar HTML | Use a local/system font stack and prove zero unexpected egress under an offline network test |
| SEC-010 | Sidecar dependency tree contains high advisory `GHSA-qwww-vcr4-c8h2` | The current client does not use the affected unstable RSC API, so record a temporary VEX; then remove React Router or upgrade to a patched line and make the audit gate clean |
| SEC-011 | No PR CI, dependency policy, security policy, full secret scanner, or release SBOM exists | Add the secure-SDLC gates in section 8 before a pilot build |
| SEC-012 | Request bodies, generated source, cache entries, and bridge responses do not have one documented, centrally enforced limit policy | Set limits, timeouts, rate controls, TTLs, and bounded parsing behavior; test rejection without resource exhaustion |
| ARCH-001 | Mode B accepts bridge-provided Python | Keep Mode B experimental/off by default until the IR/compiler/validator path is the only generation route |

### P1 — required before general availability

| ID | Finding | Required outcome |
|---|---|---|
| REL-001 | Capability persistence writes directly to the final file | Use atomic replace, checksum/schema validation, last-known-good rollback, lock/concurrency handling, and corruption tests |
| REL-002 | Process-global snapshots and caches are not multi-worker durable | Eliminate them or move state to a platform-backed, scoped store with explicit lifecycle |
| REL-003 | Broad exception swallowing can hide degraded behavior | Log structured failures, distinguish expected fallbacks, and expose degradation in self-test/GapReport |
| REL-004 | Historical SOAR-6 Python migration added privileged shell/bridge surface outside the declared SOAR 8.5 support boundary | Retired from the packaged app; the old action returns a stable unsupported-operation error |
| REL-005 | The capability “done” claim exceeds the implementation | Complete the standing-spec harvest surface and prove it against supported SOAR versions |
| TRUST-001 | Legacy scaffold validation remains heuristic | Strict organization/template review now uses closed IR and hard blockers; keep legacy import lab-only until migrated |
| TRUST-002 | README says “Production” despite incomplete trust gates | Use release-stage language and publish a support matrix and known limitations |
| DOC-001 | License was MIT in `LICENSE`/README but Apache 2.0 in the app manifest and attribution | Resolved in favor of the repository's MIT `LICENSE`; package now carries license and attribution |
| DOC-002 | Docs conflict on bundled samples, paths, current versions, and source tags | Make root docs canonical, generate packaged copies, and fail CI on drift/broken commands |

## 5. Technology decision register

This register elevates places where the current technology is questionable or a simpler alternative is preferable.

| Decision | Recommendation | Rationale and exit test |
|---|---|---|
| Splunk REST handler | **Keep, with a hardened route/service boundary** | It is the supported integration point for the embedded UI. It does not provide normal Django session/user middleware, so authentication must be explicit. Route parsing, auth, policy, and application services must be separately testable. |
| Python 3.13 | **Keep as first target** | It aligns with SOAR 8.5's forward runtime. Test on the exact supported on-prem/cloud versions; do not infer compatibility from local CPython alone. |
| React + TypeScript + Vite | **Keep** | The UI is already substantial and the stack provides useful type/build checks. A rewrite would add risk without improving the core trust model. |
| Node.js build runtime | **Use Node 24 LTS** | Node 20 reached end of life in March 2026. CI, releases, `.nvmrc`, and package engines must agree on a supported LTS line. |
| Vite 6.4 → 8.x | **Plan a separate migration** | Vite 6.4 still receives security backports. Vite 8 replaces the production bundler with Rolldown, so upgrade it in an isolated compatibility change with byte/output and browser regression evidence. |
| React Router | **Removed; keep native typed hash routing** | Four hash views did not justify the dependency or audit surface. Reconsider a router only if nested/data routes materially outgrow the current implementation. |
| Highlight.js | **Keep narrowly** | It is lighter than Monaco/CodeMirror for read-only preview. Treat its HTML output as the only trusted `dangerouslySetInnerHTML` source, pin it, and test hostile source strings. Do not add a heavyweight editor until editing is a proven requirement. |
| HTML bootstrap | **Keep the hardened escaped bootstrap; prefer JSON if it grows** | Bootstrap values now pass a context-safe serializer and CSP forbids inline script. Move to a same-origin JSON endpoint if bootstrap data becomes structurally complex. |
| `urllib` network calls | **Consolidate, not automatically replace** | Standard-library HTTP minimizes offline runtime dependencies. Build one reviewed transport adapter with TLS verification, CA support, scheme/host allowlists, redirect policy, size limits, and consistent errors. Do not keep multiple ad hoc clients. |
| `httpx` | **Keep only in developer validation tooling and pin it** | It is useful for E2E scripts but is not the app's runtime transport. Move dev dependencies to a locked requirements file; do not imply it is bundled into the SOAR app. |
| Runtime Pydantic/jsonschema | **Avoid initially** | Use standard-library dataclasses as the IR source of truth and generate JSON Schema/GBNF from them. Add a runtime dependency only if the resulting validation code is less trustworthy than a vendored, pinned library. |
| Python as template source | **Replace with versioned IR** | Organization and built-in templates should be data, not executable source. Provide a one-time migration tool and reject arbitrary code nodes except allowlisted helpers. |
| Python-to-visual heuristic parsing | **Replace with dual compilation from IR** | Heuristics inevitably drift. Python and visual JSON must be sibling outputs with the same IR hash. |
| IR `join(all)` without a fork node | **Block in preflight for IR 1.0** | Existing branching selects one edge, so an all-predecessor join cannot naturally complete. Add a typed fork/parallel construct before claiming this topology is supported. |
| Static destructive-action names | **Temporary fail-closed policy** | Require an upstream prompt for known block/disable/quarantine actions now; replace the static catalog with harvested, reviewable risk metadata before GA. |
| In-memory draft/snapshot state | **Removed from trusted design** | Shared draft state was eliminated. Trusted review is stateless; the future import API still needs an actor-bound idempotency token and durable audit record. |
| Validation console | **Keep as a developer tool, not product UI** | It provides useful environment validation without burdening the shipped sidecar. Its build and dependencies remain separately gated. |
| Duplicated packaged docs | **Generate, do not hand-maintain** | Root `docs/` is canonical. Package assembly copies a declared set and CI verifies byte equality and links. |

## 6. Ordered delivery plan

Security foundation work is a cross-cutting gate before further feature exposure; it does not reorder the standing spec's module sequence.

### Gate 0 — contain current risk and establish a trustworthy build

**Work**

- Disable Mode B by default and label it experimental in UI and docs.
- Resolve SEC-001 through SEC-012.
- Remove public font requests.
- Make build inputs locked and reproducible.
- Add PR CI, `SECURITY.md`, threat model, support matrix, dependency policy, and initial SBOM.
- Correct version, license, path, sample-data, and “production” documentation conflicts.
- Separate public errors from protected diagnostic logs.

**Tests**

- Route/method/auth matrix, negative authorization tests, CSRF/origin tests, SSRF corpus, XSS corpus, request-size and rate-limit tests.
- Two simulated users cannot read, import, overwrite, or run each other's draft.
- Restart/multi-worker tests do not lose or cross-contaminate authorized state.
- Network capture with Mode A/air-gapped enabled shows no unexpected DNS or outbound connection.
- Clean checkout builds the same logical artifact twice and validates package contents.

**Success criteria**

- Zero open critical/high *reachable* dependency findings.
- Any non-reachable advisory has a reviewed VEX with evidence, owner, and expiry.
- No unauthenticated or insufficiently authorized mutation succeeds.
- No secret or traceback appears in UI/API output or standard audit artifacts.
- All build, unit, security, and packaging checks run in PR CI.

### Gate 1 — complete capability index (standing-spec step 1)

**Work**

- Harvest roles/permissions, custom lists, existing playbooks, live CEF fields, and verified vocabularies.
- Confirm exact REST endpoints on every supported SOAR version.
- Preserve `first_seen`, `last_verified`, app version, source, health, and harvest provenance.
- Add resumable/atomic refresh, locking, last-known-good recovery, scheduled refresh, and explicit staleness policy.
- Validate baseline provenance and maintain egress/substitution data through review.

**Tests**

- Contract fixtures for each supported SOAR response shape.
- Partial page, timeout, corrupt response, permission-denied, concurrent rebuild, disk-full, truncated file, and offline cases.
- Baseline/live merge property tests and stable index hash tests.

**Success criteria**

- 100% of required standing-spec capability classes are represented or explicitly reported unavailable.
- A failed refresh never destroys the last good index.
- Unknown egress remains `unknown`; it is never silently treated as safe.
- Index state and age appear in self-test and every generated GapReport.

### Gate 2 — strict IR (standing-spec step 2)

**Work**

- Implement typed nodes, bindings, edges, metadata, schema versioning, and migration.
- Generate JSON Schema and GBNF from one source.
- Convert built-in templates to canonical IR.
- Define an allowlist for helper/code nodes; reject arbitrary Python.

**Tests**

- Positive/negative schema corpus, graph fuzzing, migration tests, canonical serialization, and hash stability.
- Every built-in template validates as IR.

**Success criteria**

- Invalid graphs and free-form code cannot cross the IR boundary.
- Serialization is deterministic and backward-compatible for the published schema window.
- Schema and grammar drift check is automatic.

### Gate 3 — deterministic compiler (standing-spec step 3)

**Work**

- Compile IR to Python and Visual Playbook Editor JSON.
- Build structured datapaths and callbacks; emit node-level debug/audit breadcrumbs.
- Record IR hash, index version, compiler version, and prompt/model provenance.
- Implement IR → outputs → parsed IR round trip.

**Tests**

- Golden files, byte-determinism, round-trip property tests, syntax/AST tests, visual/Python semantic parity, and fixture execution with mocked Phantom APIs.

**Success criteria**

- Same normalized IR and build metadata produce byte-identical artifacts.
- 100% of supported constructs round-trip without semantic change.
- Python and visual artifacts carry the same IR hash and node inventory.

### Gate 4 — validator and GapReport (standing-spec step 4)

**Work**

- Implement action, asset, parameter, datapath, permission, egress, object, graph, and staleness rules.
- Ship deterministic remediation knowledge and offline substitution details.
- Split blocker, warning, and informational policy by operating mode.

**Tests**

- One or more seeded fixtures for every gap ID, multi-gap combinations, false-positive controls, and exact remediation snapshots.
- Property tests guarantee the prose renderer cannot add entities not present in the report.

**Success criteria**

- Every failed build returns a schema-valid `GapReport`.
- Seeded gap precision and recall are both at least 0.98 before pilot.
- No blocked condition can be bypassed by model prose or UI state.

### Gate 5 — first no-model eval corpus (standing-spec step 5)

**Work**

- Add at least 30 fixtures across core SOC workflows, destructive actions, ambiguity, and impossible requests.
- Exercise capability → IR → compiler → validator without an LLM.

**Success criteria**

- IR schema validity: 100%.
- Compile success for valid fixtures: 100%.
- Expected gap-ID match: 100% on deterministic seeded defects.
- Offline run: 100% with network disabled.

### Gate 6 — constrained model path (standing-spec step 6)

**Offline implementation status:** provider, decoder, bounded repair, terminal
GapReport IDs, and scripted adversarial suite are implemented. Real endpoint
and weakest-supported-model qualification remain open.

**Work**

- Implement a narrow provider interface for in-boundary OpenAI-compatible endpoints.
- Support custom CA, TLS verification, endpoint auth, strict timeouts, response limits, and capability probing.
- Generate IR only through schema/grammar constraints and a bounded repair loop.
- Return a blocked GapReport after repair exhaustion.

**Tests**

- Invalid JSON, schema drift, hallucinated actions, slow/stalled/oversized responses, certificate errors, endpoint loss, and repair exhaustion.
- Test at least one weakest-supported local model, not only a frontier service.

**Success criteria**

- Zero model-generated Python reaches compilation/import.
- 100% of accepted model output is schema-valid IR.
- Provider failure never changes or imports a draft.
- Model/provider/prompt versions are recorded without logging prompts that contain secrets or sensitive case data.

### Gate 7 — deterministic retrieval (standing-spec step 7)

**Offline implementation status:** BM25, bounded retrieval bundles, canonical
IR template library, optional fusion primitive, and the initial lexical recall
gate are implemented. Organization-reviewed corpus expansion remains open.

**Work**

- Implement offline BM25 over the local capability index and IR templates.
- Retrieve bounded action/template candidates; never send the full capability catalog.
- Keep embeddings optional and disabled by default.

**Success criteria**

- Top-5 action recall at least 0.95 on the approved intent corpus.
- Retrieval works with no model and no network.
- Optional embeddings cannot change safety/validation policy.

### Gate 8 — full corpus and weakest-model qualification

**Work**

- Expand to at least 100 fixtures covering all documented workflows and seeded failures.
- Run connected, restricted, and air-gapped policies.
- Publish per-model evidence rather than a generic “AI works” claim.

**Initial quality thresholds**

| Metric | Pilot | General availability |
|---|---:|---:|
| IR schema validity after repair | ≥ 98% | ≥ 99.5% |
| Action-resolution accuracy | ≥ 95% | ≥ 98% |
| Required-parameter binding accuracy | ≥ 95% | ≥ 98% |
| Compile success for valid IR | 100% | 100% |
| Gap precision / recall | ≥ 0.95 / 0.95 | ≥ 0.98 / 0.98 |
| Unsupported request safely blocked | 100% | 100% |
| Offline deterministic fixtures | 100% | 100% |

### Gate 9 — offline package, self-test, and release engineering

**Work**

- Vendor only required runtime wheels with exact hashes/platform tags.
- Generate CycloneDX or SPDX SBOMs for the app, sidecar, and validation tooling.
- Add provenance, checksums/signatures, package allowlist, install/upgrade/rollback verification, and disaster-recovery runbook.
- Extend self-test to cover index, compiler round-trip, known-bad GapReport, TLS/CA, filesystem health, and optional model endpoint.

**Success criteria**

- Install succeeds on a clean supported SOAR instance with no internet.
- Package contains only allowlisted files and no dev/test cache, source map, credential, or unexpected executable.
- Upgrade preserves supported config/content; rollback is demonstrated.
- Self-test detects every seeded broken prerequisite and gives offline-capable remediation.

### Gate 10 — human review UI and production UX

**Work**

- Show intent → IR diff → gap report → compiled artifacts → import as an explicit review sequence.
- Present destructive actions, egress, unknowns, asset mappings, and substitutions prominently.
- Fix literal Markdown leakage, nested scrolling, clipped tablet layout, and excessive Help density.
- Define and implement accessible responsive behavior and keyboard navigation.
- Give Coach/Tutor claims citations to capability/index or case evidence.

**Tests and success criteria**

- WCAG 2.2 AA automated checks plus keyboard/screen-reader manual review.
- No unlabeled control, focus trap, contrast failure, or status conveyed only by color.
- No clipping or hidden primary action at 1280×720 and 1440×900.
- At 1024×768, the UI is usable or displays an explicit minimum-width handoff.
- No literal formatting markers appear in rendered user-facing messages.
- Destructive import/run requires a fresh, unambiguous confirmation and states exact actions/target.
- Five representative analysts complete Build → Review → Import without facilitator help in usability testing; critical error rate is zero.

## 7. Test strategy

| Layer | Scope | Merge/release rule |
|---|---|---|
| Unit | Pure schemas, parsing, compilers, validators, URL policy, auth policy | Every PR |
| Property/fuzz | IR graphs, datapaths, serializers, hostile strings, malformed REST/model responses | Every PR with bounded seeds; extended nightly |
| Contract | Recorded, sanitized SOAR API shapes by supported version | Every PR |
| Component | React states, confirmations, error and gap rendering | Every PR |
| Browser E2E | Studio/assistant/coach/tutor; Build/Run/Help; keyboard/a11y; responsive sizes | Every PR on core flows |
| Integration | Supported SOAR lab, representative apps/assets, auth roles | Nightly and release candidate |
| Runtime | Import, VPE parity, run, output assertions, cleanup | Release candidate |
| Resilience | Bridge down, restart, concurrent user, timeout, partial write, stale/corrupt index | Nightly and release candidate |
| Performance | Index build, compile, validation, UI load, 95th/99th percentile latency and memory | Release candidate with budgets |
| Security | SAST, dependency, secrets, license, SBOM, SSRF/XSS/CSRF/authz tests | Every PR; extended nightly |
| Packaging | Clean build, file allowlist, reproducibility, install, migration, rollback | Every release |

### Required environment matrix

Each supported journey is tagged and exercised across the applicable matrix:

- mode: `air_gapped`, `restricted`, `connected`;
- generation: template, local deterministic NL, weakest supported model;
- persona: studio, assistant, coach, tutor;
- user: viewer/analyst, playbook author, administrator;
- state: fresh install, configured, stale index, missing asset, bridge down, upgrade;
- viewport: 1280×720, 1440×900, and minimum-width behavior;
- platform: every declared SOAR/Python combination.

## 8. Vulnerability and secure-SDLC policy

### Required automation

- `pytest`, capability/eval gates, TypeScript builds, browser tests, and package verification;
- `pip-audit` against locked developer/runtime inputs;
- `npm audit` plus an OSV or equivalent cross-check;
- Bandit and CodeQL or Semgrep with a reviewed baseline;
- `gitleaks` on the full Git history and PR diff;
- license compatibility and SBOM generation;
- Dependabot or Renovate with grouped, tested updates;
- release artifact malware/content scan and checksum verification.

### Triage policy

| Condition | Policy |
|---|---|
| Reachable critical/high | Blocks merge and release |
| Non-reachable critical/high | Requires VEX, evidence, security owner, compensating controls, and expiry |
| Medium in exposed trust boundary | Blocks release unless fixed or time-bound risk acceptance is approved |
| Low/static-analysis finding | Fix, suppress with line-specific rationale, or track with owner |
| Unknown egress or dependency provenance | Treated as unsafe until classified |

Scan on every PR, nightly against updated advisory data, and again while producing a release candidate. Publish a private disclosure process in `SECURITY.md`; do not put exploitable detail in public issues before a fix is available.

### Threat-model trust boundaries

At minimum model:

- browser/analyst ↔ SOAR REST handler;
- REST handler ↔ SOAR REST loopback;
- REST handler ↔ optional MCP/model bridge;
- configuration/secrets ↔ UI/export/logs;
- local capability index ↔ generator/compiler;
- user/model-provided IR ↔ validator/compiler;
- compiled artifact ↔ import/run;
- ES deep link ↔ case/context selection;
- package source ↔ release archive ↔ installed SOAR runtime.

## 9. Reliability, resilience, and observability

Define structured events for build, validation, import, run, index refresh, bridge calls, authorization denial, and policy decisions. Events use correlation IDs and record hashes/versions, duration, result code, and actor scope where the platform makes it available. They never record tokens, credentials, full case payloads, or unredacted prompts by default.

Initial service objectives for a supported lab/pilot environment:

| Objective | Target |
|---|---:|
| Deterministic template build + validation p95 | ≤ 2 seconds |
| Sidecar initial interactive load p95 on supported network | ≤ 3 seconds |
| Import request duplicate side effects | 0 |
| Cross-user draft leakage | 0 |
| Unexpected egress in air-gapped mode | 0 |
| Last-good capability index loss after failed refresh | 0 |
| Public responses containing secrets/tracebacks | 0 |
| Unclassified failure response | 0; every error has stable code/correlation ID |

Latency targets should be re-baselined on supported SOAR hardware before general availability.

## 10. Documentation and release truth

Before pilot:

- choose MIT or Apache-2.0 and make `LICENSE`, manifest, README, and attribution agree;
- replace stale versions (`2.7.2`, `v2.22.0`) with generated current-version references where appropriate;
- remove stale `packaging/soar-playbook-builder-app` working-directory instructions;
- state clearly that sample cases are metadata shipped for optional demo provisioning, not pre-created customer containers;
- make root docs canonical and generate the packaged subset;
- publish supported SOAR/Python/browser/model matrices;
- replace “Production” claims with the actual release stage until all gates pass;
- publish known limitations, data-flow/egress behavior, backup/rollback steps, and vulnerability reporting.

## 11. Release stages

| Stage | Entry gate | Exit evidence |
|---|---|---|
| Developer preview | Gate 0 complete | Clean CI/security baseline and documented limitations |
| Internal alpha | Gates 1–5 complete | Deterministic offline template system and 30-fixture evidence |
| Model alpha | Gates 6–7 complete | Constrained IR-only model path and retrieval evidence |
| Pilot | Gates 8–9 complete | 100+ fixtures, weakest-model/offline results, certified install/upgrade |
| Release candidate | Gate 10 complete | Human review UX, accessibility/usability, live SOAR runtime suite |
| General availability | All P0/P1 closed and sign-off complete | Security, product, platform, operations, and documentation approvals |

## 12. Immediate execution backlog

The remaining sequence starts where offline evidence ends:

1. Capture authenticated principal/role/request behavior on the target SOAR
   instance and implement deny-by-default authorization from verified signals.
2. Harvest and sanitize supported-version REST contracts for apps, actions,
   assets, permissions, objects, vocabularies, import, and run.
3. Qualify compiler visual JSON against native VPE output, beginning with Hello.
4. Design the strict import transaction: actor-bound approval, commit-time hash
   revalidation, idempotency, isolation, audit, and rollback.
5. Run safe live imports/runs on disposable cases, then integration and
   destructive tiers with dedicated test assets.
6. Qualify one named weakest local model/runtime through the constrained
   provider and expand the corpus to 100+ reviewed fixtures.
7. Expand the component and Chromium CI now in place into the supported-browser
   matrix, manual keyboard/screen-reader review, and analyst usability evidence.
8. Migrate Vite 6.4 to 8.x in a separate compatibility change; CI/release
   already use supported Node 24 LTS.
9. Add signed build provenance and live clean-install/upgrade/rollback evidence.

No new model or import feature should outrun these gates.

## 13. External decisions to confirm

- Which SOAR deployment(s) are the first certification targets: on-premises, cloud, or both?
- Which license is intended: MIT or Apache-2.0?
- Which local model/runtime is the weakest supported Mode B target?
- Which roles may build, import, run, administer config, and export config?
- Is 1200 CSS pixels an acceptable documented minimum viewport?
- Which bridge hosts/CAs are allowed in each operating mode?

These decisions affect policy and test matrices, but they do not block Gate 0 engineering work.

## References

- [Splunk: REST handlers and their request limitations](https://help.splunk.com/en/splunk-soar/soar-on-premises/develop-apps/8.4.0/develop-an-app-using-the-splunk-soar-app-wizard/app-structure/use-rest-handlers-to-allow-external-services-to-call-into-splunk-soar-on-premises)
- [Splunk: Python 3.13 direction for SOAR 8.5](https://help.splunk.com/en/splunk-soar/soar-cloud/develop-apps/build-playbooks)
- [GitHub advisory GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)
- [Node.js release schedule](https://nodejs.org/en/about/previous-releases)
- [Vite supported releases](https://vite.dev/releases)
