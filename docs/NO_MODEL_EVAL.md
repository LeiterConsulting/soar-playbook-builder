# No-model evaluation corpus

The first deterministic corpus lives under
`soar_playbook_builder/eval/corpus/`. It exercises the complete offline trust
path:

```text
typed IR -> deterministic Python + visual JSON -> round-trip -> preflight GapReport
```

It never invokes a model, a bridge, SOAR, or any network endpoint.

## Current evidence

- 40 timezone-fixed cases;
- 100% IR construction/validation;
- 100% dual-artifact compile and round-trip;
- 100% exact expected report status;
- 100% exact expected gap-ID match;
- all 31 supported deterministic gap IDs seeded;
- an explicit network-denial test around the entire corpus; and
- distinct clean, degraded, blocked, multi-gap, destructive, egress, permission,
  asset, object, staleness, and impossible-capability cases.

Representative workflows include Okta identity lookup, VirusTotal offline
substitution, Slack notification, ServiceNow ticketing, custom-list write,
child-playbook invocation, container severity changes, and Active Directory
account disable with and without an upstream analyst prompt.

The capability indexes in this corpus are synthetic test evidence. They are
clearly marked `test-only` and must never be interpreted as claims about an
installed customer environment.

## Success metrics

The harness fails on the first mismatch. It does not average away a safety
failure:

| Metric | Required |
|---|---:|
| Valid fixture IR | 100% |
| Compile + Python round-trip | 100% |
| Compile + visual round-trip | 100% |
| Expected status match | 100% |
| Expected gap-ID match | 100% |
| Supported gap-ID coverage | 100% |
| Network calls | 0 |

## Run

```bash
python3 soar_playbook_builder/eval/harness.py --suite corpus
python3 -m pytest -q tests/test_no_model_corpus.py
```

`--suite all` includes capability, IR, compiler, validator, corpus,
model-boundary, and retrieval gates.

## Limits

This corpus proves deterministic internal behavior, not live SOAR compatibility
or natural-language planning accuracy. It does not replace:

- migration of every shipped Python template to manually reviewed canonical IR;
- sanitized SOAR REST contract fixtures by supported version;
- live permission, asset, object, VPE, import, and runtime evidence;
- weakest-supported local-model qualification; or
- the eventual 100+ full corpus with measured action/parameter selection.
