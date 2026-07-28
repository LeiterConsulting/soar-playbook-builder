# Air-Gap-Capable Splunk SOAR Playbook Builder — standing spec

> **Project copy:** Module paths use `soar_playbook_builder/` (see [AGENTS.md](../AGENTS.md)). Cursor rule: `.cursor/rules/air-gap-playbook-builder.mdc`.

---

## ROLE

You are implementing a Splunk SOAR app that generates SOAR playbooks from natural language and from a built-in template library. The app must function identically whether or not the host has internet access. Assume the production deployment is fully air-gapped and that the backing LLM may be a small local model or a customer-built model of unknown quality.

Work incrementally. After each module, run the eval harness (Section 11) and report pass/fail before moving on. Do not skip ahead to features while foundational modules are unvalidated.

---

## 1. NON-NEGOTIABLE ARCHITECTURE PRINCIPLES

Apply these to every design decision. If a proposed implementation violates one, stop and flag it rather than working around it.

1. **The LLM is never the source of truth about SOAR capabilities.** All knowledge of apps, actions, parameters, datapaths, and assets comes from introspecting the local SOAR instance. The model's parametric memory is treated as unreliable and is never trusted for factual claims about the environment.
2. **The LLM never emits playbook Python.** It emits a constrained intermediate representation (IR). A deterministic compiler renders the IR into playbook code and playbook JSON.
3. **Correctness checks are deterministic.** Validation, gap detection, and remediation instructions are generated from schema data, not from the model. The model may only rephrase a structured report into prose.
4. **No runtime network egress is assumed or required.** Any code path that would fail without internet is a defect.
5. **Assume the weakest supported model.** Every prompt, schema, and retry path must work with a ~7B quantized local model. If something only works on a frontier model, it is not shipped as a dependency.
6. **Fail loudly and specifically.** "I can't build that" is unacceptable output. The app returns either a compiled playbook or a structured gap report naming exactly what is missing and how to resolve it offline.

---

## 2. TARGET MODULE LAYOUT

Create this structure. Keep module boundaries strict — no module reaches past its neighbor.

```
soar_playbook_builder/
  __init__.py
  app.json                     # SOAR app manifest
  playbook_builder_connector.py# SOAR app entry point / action handlers
  wheels/                      # vendored dependencies (no pip at install time)

  capability/
    introspect.py              # SOAR REST harvesting
    index.py                   # build/load/persist the capability index
    schema.py                  # capability index dataclasses
    baseline/                  # build-time snapshot shipped with the app
      apps.json
      cef.json
      egress_tags.json

  ir/
    schema.py                  # playbook IR dataclasses + JSON Schema
    grammar.py                 # GBNF / JSON-Schema emitters for constrained decode

  compiler/
    render_python.py           # IR -> playbook .py
    render_visual.py           # IR -> playbook JSON (visual editor)
    datapath.py                # datapath construction + resolution helpers

  validate/
    preflight.py               # IR -> GapReport
    rules/                     # one file per rule class
    report.py                  # GapReport schema + remediation formatter

  retrieve/
    bm25.py
    embed.py                   # optional, feature-flagged
    hybrid.py
    templates/                 # built-in playbook templates as IR documents

  llm/
    provider.py                # abstract provider interface
    openai_compat.py           # Ollama / vLLM / llama.cpp / BYO endpoint
    decode.py                  # constrained decode + repair loop
    prompts/                   # versioned prompt templates

  eval/
    corpus/                    # NL request -> expected IR fixtures
    harness.py
    report.py
```

---

## 3. CAPABILITY INDEX (build this first)

### 3.1 Harvesting

Implement `capability/introspect.py` to read from the local SOAR REST API only. Verify exact endpoint paths against the target platform version before relying on them; do not hardcode assumptions you have not confirmed.

Harvest at minimum:

| Source | Purpose |
|---|---|
| Installed app list + per-app JSON | actions, parameters, `data_type`, `contains`, `required`, output datapaths |
| Configured assets | which apps are actually usable, which are configured but unhealthy |
| CEF field catalog | valid artifact field names and their `contains` types |
| Existing playbooks | naming conventions, reusable subroutines, repo layout |
| Roles / permissions | whether the executing user can run a given action |
| Custom lists | referenceable data sources for allow/deny logic |
| Severity, status, and label vocabularies | valid enum values for container updates |

Harvesting runs on app install, on demand via a SOAR action (`rebuild capability index`), and on a configurable schedule. It must be resumable and must never block playbook generation — if the index is stale, generation proceeds against the last good index and the staleness is surfaced in the gap report.

### 3.2 Baseline + diff

Ship `capability/baseline/` as a build-time snapshot of common apps and their action surfaces. On first run, diff the live harvest against the baseline and persist a merged index. Track for every capability:

- `source`: `baseline` | `discovered` | `merged`
- `first_seen` / `last_verified` timestamps
- `app_version` (never assume action signatures are stable across versions)

### 3.3 Egress tagging

Every action carries `requires_egress: true | false | unknown`. Populate from `capability/baseline/egress_tags.json` for known apps; default to `unknown` for discovered apps and surface `unknown` as a warning, never silently as `false`.

Implement a substitution map: for common egress-dependent actions, define offline equivalents (e.g. external reputation lookup → local threat-intel index or custom list lookup). When the app is configured in air-gapped mode, the planner must prefer substitutes and explicitly report every substitution it made.

---

## 4. PLAYBOOK IR

Define in `ir/schema.py` with a strict JSON Schema. The model produces **only** this. Keep it small enough that a 7B model can fill it reliably.

Required node types: `start`, `action`, `decision`, `filter`, `format`, `prompt` (HITL), `code` (allow-listed helpers only), `join`, `end`.

Every `action` node must carry:

- `app` and `action` names resolved against the capability index
- `asset` (or an explicit `asset_unbound` marker)
- `parameters`: map of param name → binding, where a binding is a literal, a datapath reference, or a reference to a prior node's output
- `on_success` / `on_failure` edges

Rules to enforce in the schema itself where possible, and in the validator otherwise:

- No free-form Python in `action` nodes
- Datapath references are structured objects (`{source_node, path}`), not raw strings — the compiler builds the string
- Every non-terminal node has at least one outbound edge
- Graph is acyclic unless an explicit loop construct is used

Emit the schema in two forms: JSON Schema for schema-guided decoding, and GBNF grammar for llama.cpp-class runtimes. Generate both from the same source of truth so they cannot drift.

---

## 5. COMPILER

`compiler/` converts IR → playbook artifacts. It contains **zero** model calls.

Requirements:

- Deterministic: same IR always produces byte-identical output
- Produces both the playbook `.py` and the visual-editor JSON, and they must be mutually consistent
- Generates correct callback wiring, action result handling, and datapath strings from structured bindings
- Emits `phantom.debug` breadcrumbs at each node for runtime traceability
- Injects a header comment recording the IR hash, capability index version, model and prompt version used, and generation timestamp
- Round-trip test: compiled playbook → parse → IR must equal input IR for all supported constructs

---

## 6. PREFLIGHT VALIDATOR AND GAP REPORT

`validate/preflight.py` takes an IR plus the capability index and returns a `GapReport`. This is the module that makes the app useful offline — invest here.

### Rule classes to implement

1. **Action resolution** — action exists in an installed app at a compatible version
2. **Asset binding** — a configured asset exists for the app; if not, list required configuration keys extracted from the app JSON
3. **Parameter completeness** — all `required` params bound; types match `data_type`; `contains` types are compatible between producer and consumer
4. **Datapath resolvability** — every referenced datapath resolves against a prior node's declared outputs, or against the container/artifact CEF catalog
5. **Permission** — executing role can run the action and mutate the target objects
6. **Egress** — flags any `requires_egress: true` or `unknown` action when air-gapped mode is on, with substitution offered
7. **Referenced objects** — custom lists, labels, severities, and playbooks referenced by name actually exist
8. **Graph integrity** — unreachable nodes, dangling edges, missing failure paths, unjoined parallel branches
9. **Index staleness** — index older than threshold, or harvest last failed

### GapReport structure

```json
{
  "status": "ok | degraded | blocked",
  "gaps": [
    {
      "id": "ASSET_MISSING",
      "severity": "blocker | warning | info",
      "node": "<ir node id>",
      "summary": "<one line, generated from schema data>",
      "detail": { "app": "...", "required_config_keys": ["..."] },
      "remediation": {
        "offline_capable": true,
        "steps": ["ordered, literal, copy-pasteable steps"],
        "artifacts_needed": [
          {"type": "app_package", "name": "...", "version": "...", "splunkbase_id": "...", "transfer_note": "..."}
        ]
      }
    }
  ],
  "substitutions": [],
  "index_version": "...",
  "index_age_seconds": 0
}
```

**Every field above is produced deterministically.** The remediation steps are templated from the capability index and a static remediation knowledge base shipped with the app — never generated by the model. The model's only permitted involvement is rendering the finished `GapReport` into readable prose, and it must not add, remove, or alter any fact in it. Enforce this by diffing entities in the prose against the report and rejecting hallucinated additions.

Cache Splunkbase app IDs, version metadata, and download filenames at build time into the shipped remediation knowledge base, so an air-gapped user is told exactly which package to transfer in.

---

## 7. RETRIEVAL LAYER

Generation quality must come from retrieval, not model size.

- Implement BM25 over action names, descriptions, parameter names, and template metadata. This is the default and must work with no model and no embeddings.
- Optionally add a local embedding model behind a feature flag for fuzzy intent matching. Hybrid-rank with reciprocal rank fusion. The app must remain fully functional with embeddings disabled.
- On each request, retrieve top-N candidate actions from the live capability index and top-K nearest templates from `retrieve/templates/`.
- Inject retrieved templates as in-context IR exemplars. Templates are stored as IR documents, not as Python, so they double as compiler test fixtures.
- Never place the full action catalog in context. Retrieval scope is the mechanism that keeps a small model accurate.

---

## 8. MODEL PROVIDER ABSTRACTION

`llm/provider.py` defines a narrow interface: `generate(messages, schema=None, grammar=None, **opts) -> str`.

- Primary implementation targets an OpenAI-compatible `/v1/chat/completions` endpoint. This covers Ollama, vLLM, llama.cpp server, and customer-built in-boundary models.
- Configurable: base URL, model name, auth header, timeout, **custom CA bundle path**, and TLS verification mode. Do not rely on the platform's bundled Python CA bundle — allow an explicit override, since internal CAs are frequently absent from it.
- **Do not depend on native tool-calling or function-calling APIs.** Many in-boundary models lack reliable support. Structured output comes from constrained decoding or from schema-validated retry.
- Capability probe at configuration time: detect whether the endpoint supports grammar/JSON-schema constrained decode, and record the result. Degrade to the repair loop when it does not.

### Repair loop (`llm/decode.py`)

1. Attempt constrained decode against the IR schema.
2. If unavailable or output fails schema validation, re-prompt with the validator's structured error appended, bounded to N attempts.
3. If still failing, return a `blocked` GapReport explaining that the model could not produce a valid plan — never return partial or invented playbook code.

Version every prompt template and record the version in generated playbook headers.

---

## 9. OPERATING MODES

Expose a single configuration value with three states:

- `air_gapped` — egress actions blocked, substitutions preferred, remediation assumes manual package transfer
- `restricted` — egress actions allowed but flagged for approval
- `connected` — full capability, but the code path is otherwise identical

Identical code path across modes is a hard requirement. Mode changes behavior only through policy checks in the validator and planner, never through alternate implementations.

---

## 10. PACKAGING FOR OFFLINE INSTALL

- Vendor **all** Python dependencies as wheels under `wheels/`, referenced from `app.json` `pip3_dependencies`. There is no pip at install time on a closed network.
- Match the wheel platform tags and Python version to the target SOAR platform exactly. Confirm the Python version for the specific SOAR release you are targeting; do not assume it carries across minor versions.
- Model weights are **not** bundled. They are a separate transfer artifact with a configurable path or endpoint.
- The baseline capability index, remediation knowledge base, and template library ship inside the app tarball.
- Provide a self-test SOAR action that verifies: index loads, model endpoint reachable, TLS/CA valid, compiler round-trips a known IR, and validator produces the expected gap report on a deliberately broken fixture.

---

## 11. EVAL HARNESS (build early, run continuously)

`eval/harness.py` is a gating dependency, not a nice-to-have. Build a first version before the retrieval layer.

- Corpus of ≥100 natural-language requests spanning: phishing triage, endpoint containment, IOC enrichment, ticket creation, user disable/enable, network block, notable-event handling, HITL approval flows, and deliberately impossible or ambiguous requests.
- Each fixture: `request` → `expected_ir` (or `expected_gap_report` for the impossible cases).
- Metrics: IR schema validity rate, action-resolution accuracy, parameter-binding accuracy, compile success rate, gap-report precision/recall on seeded defects, and end-to-end pass rate.
- **Run the suite with the network interface down and against the weakest supported model.** A pass on a frontier model with internet is not evidence of anything.
- Seed-defect fixtures: environments with a missing app, unconfigured asset, insufficient role, and stale index — assert the exact expected gap IDs and remediation steps.
- Wire into CI. Regressions block merge.

---

## 12. IMPLEMENTATION ORDER

Do not reorder. Each step gates the next.

1. `capability/` — schema, introspection, baseline, index persistence, diff
2. `ir/` — schema, JSON Schema + GBNF emitters
3. `compiler/` — Python + visual JSON rendering, round-trip tests
4. `validate/` — rules, GapReport, remediation knowledge base
5. `eval/` — harness plus first 30 fixtures, run against steps 1–4 with no model in the loop
6. `llm/` — provider abstraction, constrained decode, repair loop
7. `retrieve/` — BM25, template library as IR, hybrid ranking behind a flag
8. Full corpus to ≥100 fixtures, offline runs, weakest-model runs
9. SOAR app packaging, wheel vendoring, self-test action
10. HITL review UI: show IR diff, gap report, and compiled output before commit to the playbook repo

---

## 13. EXPLICIT ANTI-REQUIREMENTS

Do not:

- Call any external service at runtime, including for model inference unless explicitly configured to an in-boundary endpoint
- Let the model write, edit, or patch playbook Python directly
- Let the model author remediation steps or claim an app/action exists
- Silently fall back to a smaller feature set without reporting it
- Assume action signatures are stable across app versions
- Put the full action catalog in the model context
- Bundle model weights in the app package
- Treat `requires_egress: unknown` as `false`
- Ship a feature that has no corresponding eval fixture

---

## 14. DEFINITION OF DONE

The app is done when, with the host network interface disabled and a 7B quantized local model:

1. The full eval corpus passes at the agreed threshold.
2. Every seeded-defect fixture produces the exact expected gap ID and remediation steps.
3. A user request naming an app that is not installed yields step-by-step offline install instructions including the exact package to transfer.
4. Compiled playbooks import cleanly into SOAR, appear correctly in the visual editor, and execute against a test container.
5. The self-test action passes on a fresh install with no internet.
