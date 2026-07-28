# Deterministic preflight and GapReport contract

`soar_playbook_builder/validate/` validates a typed Playbook IR against one
specific capability-index snapshot. It returns a closed, versioned-shape
`GapReport`; it never calls a model or the network and never mutates the IR.

## Status policy

- `blocked`: at least one blocker exists. The IR must not be imported or run.
- `degraded`: no blocker exists, but one or more warnings require review.
- `ok`: no blocker or warning exists.

Informational entries do not degrade status. Gaps and substitutions are sorted
canonically, so the same IR, index, evaluation timestamp, and policy threshold
produce byte-identical report JSON.

The caller must provide a timezone-aware `evaluated_at`. The validator never
reads the wall clock itself. That keeps staleness tests and signed review
artifacts reproducible.

## Rules

| Rule | Fail-closed behavior |
|---|---|
| Action resolution | Exact app/action match only; no fuzzy substitution |
| Installation evidence | Baseline entries do not prove an app/action is installed |
| Asset binding | Requires an exact, app-owned, configured, healthy asset |
| Parameters | Required, declared, literal type, and `contains` compatibility checks |
| Datapaths | CEF fields and action/local outputs must resolve from indexed declarations |
| Permissions | Missing/partial evidence blocks; browser role headers are never evidence |
| Destructive action | Known block/disable/quarantine actions require an upstream prompt |
| Egress | `true` blocks air-gapped/restricted; `unknown` blocks air-gapped and warns otherwise |
| Referenced objects | Custom lists, playbooks, and vocabulary values must be verified |
| Graph policy | IR 1.0 `join(all)` blocks because no fork primitive can satisfy it |
| Index state | Version mismatch blocks; bad/missing age and degraded harvest are surfaced |

`playbook_input` is blocked in IR 1.0 because the IR does not yet define an input
specification. This avoids accepting an input name that the compiled artifact
cannot prove exists.

SOAR-native `phantom` actions are also blocked until each action has a
live-qualified explicit compiler mapping. They are not sent through the generic
asset-action renderer.

The initial destructive-action catalog is a conservative static policy for the
shipped patterns. This is safer than omitting the gate, but the target design is
harvested action-risk metadata in the capability index so organization-specific
destructive actions do not depend on name matching.

## Capability evidence states

The capability index distinguishes:

- `verified`: inventory or permissions were harvested for the relevant target;
- `partial`: some evidence is present but incomplete;
- `unavailable`: no trustworthy evidence exists.

An empty verified inventory means “verified and empty.” An unavailable inventory
does not mean empty and cannot be used as an allow decision.

The extended index carries:

- app configuration keys;
- roles and the evaluated principal;
- per-app/action permission decisions;
- custom-list inventory;
- playbook inventory; and
- evidence status for permissions and object inventories.

The current offline baseline intentionally sets live-only evidence to
`unavailable`. A live harvest must populate it before import can pass preflight.

## Remediation and substitutions

Every supported gap ID maps to static ordered remediation steps. App-installation
gaps can name an offline package artifact, but the validator leaves unknown
Splunkbase IDs and versions empty rather than inventing them.

The report schema also closes over the model-boundary terminal IDs
`MODEL_OUTPUT_INVALID`, `MODEL_PROVIDER_FAILED`, and
`MODEL_REPAIR_EXHAUSTED`. These are created by the bounded decoder, not by
deterministic preflight rules. Their remediation remains static and model-free.

Offline egress substitutions are suggestions only:

```json
{
  "automatic": false
}
```

The validator never silently rewrites the IR. An analyst or deterministic
planner must explicitly accept a replacement and run preflight again.

## Schema

`gap_report_json_schema()` emits a closed Draft 2020-12 JSON Schema. The report
contains:

- status;
- ordered gaps with ID, severity, node, detail, and remediation;
- ordered substitutions;
- capability-index version and age;
- explicit evaluation timestamp; and
- canonical IR SHA-256.

Hash-golden tests cover exact remediation output, and an independent JSON Schema
implementation validates positive reports in CI.

## Deferred live evidence

Offline tests cannot establish:

- which principal SOAR binds to a REST-handler import/run request;
- exact role/action authorization decisions;
- current asset health and connector configuration keys;
- custom-list/playbook inventories;
- native app output metadata on the installed versions; or
- whether the target VPE/runtime preserves the compiled artifacts.

Those are gaps, not assumptions. They remain blocked until the live capability
harvest and SOAR 8.5.x qualification runs supply evidence.

## Verification

```bash
python3 soar_playbook_builder/eval/harness.py --suite validator
python3 -m pytest -q tests/test_preflight.py tests/test_gap_report.py
```
