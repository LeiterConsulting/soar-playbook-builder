# Deterministic offline retrieval contract

`soar_playbook_builder/retrieve/` grounds requests in a bounded subset of the
local capability index and shipped Playbook IR templates. It has no model,
embedding, network, database, or third-party runtime dependency.

## Lexical index

`BM25Index` implements immutable Okapi BM25 over normalized alphanumeric and
camelCase tokens. Rankings are deterministic:

- documents are indexed by stable ID;
- the same index/query produces the same floating-point scores;
- equal scores break by document ID; and
- zero-overlap documents are omitted instead of filling the result with
  arbitrary catalog entries.

Action documents include the discovered app key/name/product, action name and
description, parameter names/descriptions/types/`contains`, and declared output
paths.

## Template library

`retrieve/templates/*.json` contains one canonical IR exemplar for each of the
11 shipped pattern-catalog entries. The loader:

- permits only sorted regular `.json` files;
- rejects symlinks, oversized files, duplicate keys, non-finite constants,
  malformed JSON, invalid IR, missing template IDs, ID/filename drift, and
  duplicate IDs;
- computes the canonical IR SHA-256; and
- treats the IR itself as the compiler fixture and model exemplar.

The templates do not prove an app is installed and do not bypass preflight.
Their `asset_unbound` bindings are intentional until a specific target index
and analyst selection supply an exact asset.

## Context bounds

`OfflineRetriever.retrieve()` returns at most:

- 32 actions by hard policy (12 by generation default);
- 8 IR templates by hard policy (3 by generation default); and
- 64 assets associated only with selected apps.

The model decoder serializes this bundle, not the full action catalog. Context
also carries the capability index version and evidence-state labels. The same
deterministic validator still rejects any model output that exceeds the
retrieved or current capability evidence.

## Optional hybrid rank

`reciprocal_rank_fusion()` is available for a future local embedding ranker.
Lexical BM25 remains the required default. No embedding model is shipped or
loaded, and no remote embedding call is permitted.

## Evidence and current limit

The first lexical intent corpus contains 20 fixed requests across ServiceNow,
VirusTotal, Slack, Teams, PagerDuty, and SOAR-native actions. Its current top-5
action recall is 1.000, above the 0.95 gate.

That small synthetic corpus is regression evidence, not a general language
quality claim. Before pilot it must be expanded with organization-reviewed
wording, ambiguity, false-positive checks, installed-version variation, and
weakest-supported-model runs.

## Verification

```bash
python3 soar_playbook_builder/eval/harness.py --suite retrieval
python3 -m pytest -q tests/test_retrieval.py
```

The suite also denies socket creation, dual-compiles every template, verifies
lossless Python/visual round trips, and proves the selected context is smaller
than the full action catalog.
