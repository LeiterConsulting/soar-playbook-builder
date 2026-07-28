# Deterministic compiler contract

The compiler under `soar_playbook_builder/compiler/` converts a validated
Playbook IR document into two sibling artifacts:

1. a Splunk SOAR Python playbook; and
2. a visual JSON/COA document.

The compiler contains no model calls and does not use the network, filesystem,
randomness, process-global draft state, or current wall-clock time.

## Offline guarantees

Given the same normalized IR and compiler version:

- Python and visual JSON are byte-identical across compilations.
- Both artifacts carry the same canonical IR SHA-256.
- Both contain the complete IR and can be parsed back to an equal validated IR.
- Hash mismatches are rejected during round-trip parsing.
- Every IR node appears in the visual inventory and every graph edge carries its
  explicit semantic (`success`, `failure`, `true`, `false`, and so on).
- Structured artifact, container, playbook-input, and named action-result
  datapaths are rendered by the compiler; raw datapath strings are not accepted.
- Generated Python is syntax/AST tested and contains no `eval`, `exec`, dynamic
  import, or model-generated source.
- Each runtime node emits a correlation breadcrumb through `phantom.debug`.
- Local format, helper, prompt, join, and action callback state uses
  playbook-run-scoped block results rather than Python globals.
- An `asset_unbound` action never calls `phantom.act`; it follows its failure
  edge and records a blocked breadcrumb.

The provenance header records the compiler version, artifact schema, IR hash,
capability-index version, model, prompt version, and generation timestamp. To
preserve determinism, the compiler takes the timestamp from IR metadata. Missing
values are recorded as `unspecified`; the compiler never substitutes the current
time.

## Runtime semantics

Action callbacks store the result and select exactly one success/failure edge.
Decision and filter conditions are evaluated from typed condition objects.
Format and allowlisted helper outputs are saved under the producing node.
Prompts use `phantom.prompt2` with the `Automation` role and deterministic
multiple-choice response metadata. A failed prompt callback is treated as a
timeout, matching the current Splunk API contract. Join arrival state is scoped
to the current playbook run.

The only code helpers are the IR allowlist:

- `coalesce`
- `deduplicate_values`
- `normalize_indicator`
- `parse_iso8601`

## Visual artifact status

The JSON preserves the repository's current COA envelope and renders directly
from IR instead of reverse-parsing Python. It includes:

```json
{
  "playbook_builder": {
    "native_schema_status": "unverified_without_live_soar"
  }
}
```

That marker is intentional. Offline tests prove internal parity and lossless
round-trip, but cannot prove that a specific Splunk SOAR release will accept,
display, edit, save, export, and re-import every native node property without
normalizing or dropping it.

Do not route this artifact into production import until the live qualification
matrix below passes for the target SOAR version.

## Deferred live-SOAR qualification

The following require a licensed test instance and are not represented as
offline proof:

- import the generated Python and visual pair through the supported REST path;
- open and save it in the Visual Playbook Editor;
- export it and compare node/edge semantics with the embedded IR;
- run each node type and assert callback, action-result, prompt, timeout, and
  output behavior;
- validate `playbook_input` and named action-result datapaths on real results;
- race-test join state across automation workers;
- verify permission failures and asset health behavior;
- confirm supported Python/runtime behavior on SOAR 8.5.x.

## Known IR design issue

IR 1.0 permits `join(strategy="all")`, but it has no fork/parallel node. All
current branching nodes select exactly one outbound edge, so ordinary v1 graphs
cannot naturally activate every predecessor of an `all` join in one run. The
compiler preserves and implements arrival semantics for forward compatibility,
but the preflight validator must report this construct as blocked until the IR
adds an explicit parallel/fork construct or formally narrows join semantics.

## Verification

Run:

```bash
python3 soar_playbook_builder/eval/harness.py --suite compiler
python3 -m pytest -q tests/test_compiler.py tests/test_compiler_datapath.py
```

The tests cover golden hashes, byte determinism across reordered source nodes,
AST safety, tamper rejection, Python/visual parity, lossless round-trip, mocked
callbacks, prompts, local formatting, and fail-closed unbound assets.
