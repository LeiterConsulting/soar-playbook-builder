# SOAR Playbook Builder — agent instructions

Standing spec for AI-assisted development: **[docs/AIR_GAP_BUILD_SPEC.md](docs/AIR_GAP_BUILD_SPEC.md)**.

## Module path mapping

The spec uses `playbook_builder/`; this SOAR app ships code under **`soar_playbook_builder/`**:

| Spec path | This repo |
|-----------|-----------|
| `playbook_builder/capability/` | `soar_playbook_builder/capability/` |
| `playbook_builder/ir/` | `soar_playbook_builder/ir/` |
| `playbook_builder/compiler/` | `soar_playbook_builder/compiler/` (implemented; live VPE qualification pending) |
| `playbook_builder/validate/` | `soar_playbook_builder/validate/` (offline gate implemented; live evidence pending) |
| `playbook_builder/retrieve/` | `soar_playbook_builder/retrieve/` (offline BM25/template gate implemented) |
| `playbook_builder/llm/` | `soar_playbook_builder/llm/` (offline boundary implemented; real-model qualification pending) |
| `playbook_builder/eval/` | `soar_playbook_builder/eval/` |

Legacy sidecar + template scaffold path remains until IR/compiler replaces it (see spec §12).

## Implementation order (do not reorder)

1. **`capability/`** — schema, introspection, baseline, index persistence ← **done (2.22.0)**
2. **`ir/`** — schema, JSON Schema + GBNF emitters ← **done on foundation branch**
3. **`compiler/`** — Python + visual JSON, round-trip tests ← **offline gate done on foundation branch; live VPE qualification pending**
4. **`validate/`** — GapReport, remediation KB ← **offline gate done on foundation branch; live evidence pending**
5. **`eval/`** — harness + first 30 fixtures (no model) ← **40-case offline gate done on foundation branch**
6. **`llm/`** — provider, constrained decode, repair loop ← **offline scripted gate done on foundation branch; real-model qualification pending**
7. **`retrieve/`** — BM25, IR templates, hybrid (flagged) ← **offline gate done on foundation branch**
8. Full corpus ≥100, offline + weakest-model runs
9. Packaging, wheels, self-test action
10. HITL review UI (IR diff + gap report before commit)

## After each module

Run:

```bash
cd packaging/soar-playbook-builder-app
python3 tests/test_capability_index.py   # step 1 gate
python3 soar_playbook_builder/eval/harness.py --suite capability
```

Report pass/fail before starting the next spec section.

## Non-negotiables (summary)

- LLM never emits playbook Python — IR + deterministic compiler only.
- Capability facts come from local SOAR introspection, not model memory.
- No runtime network egress required; air-gapped mode is first-class.
- Fail with structured GapReport, not vague refusals.
