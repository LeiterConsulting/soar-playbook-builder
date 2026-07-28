# Playbook IR contract

The playbook intermediate representation (IR) is the non-executable trust
boundary between templates or future model output and the deterministic
compiler. It is implemented in `soar_playbook_builder/ir/` and currently uses
schema version `1.0.0`.

The IR is not yet connected to playbook import or execution. Existing Python
templates remain a compatibility scaffold until they are migrated through the
compiler and validator gates.

## Document shape

Every document has:

- an immutable schema version, stable document ID, name, and description;
- one `entrypoint` referencing the only `start` node;
- a bounded array of typed nodes;
- metadata naming the capability-index version and operating mode;
- optional template, model, prompt, timestamp, and label provenance.

Unknown fields and unsupported schema versions fail closed. The canonical form
sorts object keys and node IDs, rejects non-finite numbers, and produces a
stable SHA-256 digest.

## Bindings

Values enter nodes through one of three explicit binding types:

| Kind | Purpose |
|---|---|
| `literal` | Bounded JSON data; it is serialized as data and is never executed |
| `datapath` | Structured `artifact`, `container`, or `playbook_input` path segments |
| `node_output` | Structured source-node ID and output path from a prior node |

Raw datapath strings are invalid. Action nodes have no Python/source field.
`code` nodes select only one of the small helper identifiers in
`ALLOWED_CODE_HELPERS`; they cannot carry source code.

## Node and edge contract

| Node | Required outbound edges |
|---|---|
| `start` | `next` |
| `action` | `on_success`, `on_failure` |
| `decision` | `on_true`, `on_false` |
| `filter` | `on_match`, `on_no_match` |
| `format` | `next` |
| `prompt` | `on_success`, `on_failure`; optional `on_timeout` |
| `code` | `on_success`, `on_failure` |
| `join` | `next` |
| `end` | none |

The deterministic graph validator rejects duplicate IDs, missing or multiple
starts, missing ends, dangling edges, unreachable nodes, cycles, illegal branch
merges, joins with fewer than two predecessors, and node-output bindings whose
source is missing, non-producing, or not an ancestor.

Explicit loop nodes are not part of schema `1.0.0`, so all accepted graphs are
acyclic.

## Schema and constrained decoding

`ir.schema.ir_json_schema()` emits strict JSON Schema Draft 2020-12.
`ir.grammar.gbnf_grammar()` derives llama.cpp-compatible GBNF from that schema.
The GBNF fixes object property order to reduce small-model ambiguity.

GBNF cannot safely enforce every JSON Schema or graph constraint. String
lengths and patterns, collection limits, uniqueness, graph topology, and
cross-node references are always revalidated by `PlaybookIR.from_dict()`.
Constrained decoding is therefore an input-quality control, not an
authorization or correctness boundary.

The app has no runtime dependency on `jsonschema`. CI uses a pinned independent
implementation to check the emitted meta-schema and smoke fixture.

## Version evolution

Version `1.0.0` is the first published IR contract. Unsupported or missing
versions are rejected; no heuristic legacy conversion is attempted. Any future
version must add an explicit, deterministic migration with positive, negative,
and canonical-hash tests before it becomes accepted input.

## Gate commands

```bash
python -m pytest -q tests/test_ir_schema.py tests/test_ir_grammar.py
python soar_playbook_builder/eval/harness.py --suite ir
```

The next module is the deterministic compiler. It must consume `PlaybookIR`
objects only and must never accept model-provided Python.

External compatibility evidence on 2026-07-28: llama.cpp
`test-gbnf-validator` at commit
`e9fa0781f1c25fc4fe8c86be1edc6970661ad6f0` accepted the emitted grammar and
smoke IR, then rejected the same action after an undeclared `python` field was
inserted. This one-time compatibility check supplements, but does not replace,
the continuous schema/grammar drift tests.
