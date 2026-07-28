# Constrained model boundary

`soar_playbook_builder/llm/` is the only intended boundary between untrusted
model output and trusted Playbook IR.

## Provider

`ProviderConfig` and `OpenAICompatibleProvider` implement a small,
standard-library-only Chat Completions client. The client:

- permits only a configured `/v1/chat/completions` endpoint;
- validates endpoint and resolved address classes;
- disables redirects and environment proxies;
- verifies TLS by default and supports an explicit absolute CA bundle;
- separates the plain-HTTP, loopback, and unverified-TLS lab overrides;
- bounds timeout, request, aggregate message, and response sizes;
- accepts only `system`, `user`, and `assistant` text messages;
- never sends tool/function definitions; and
- maps transport/HTTP/shape failures to sanitized stable codes.

Schema and GBNF fields differ across OpenAI-compatible implementations.
`probe()` tests the configured endpoint and requires the exact constrained `{}`
response before setting a capability flag. A passing probe is evidence only for
that backend/model/configuration tuple. Generation fails closed if neither
constraint is proven; unconstrained JSON requires an explicit lab-only flag.

## Decode and repair

`generate_ir()` performs these steps:

1. retrieve and serialize a deterministic bounded subset of the local
   capability index plus canonical IR exemplars;
2. request IR using the emitted strict JSON Schema and GBNF;
3. parse exactly one JSON object, rejecting fences, duplicate keys, non-finite
   constants, and non-object roots;
4. overwrite index version, operating mode, model, prompt version, and
   generation timestamp with trusted caller values;
5. parse the closed IR contract and run deterministic preflight;
6. retry only schema issues and explicitly repairable capability blockers,
   using bounded structured issue codes; and
7. return a blocked `GapReport` when the provider fails or the repair bound is
   exhausted.

Prior raw output is not echoed into repair prompts, reports, or `DecodeResult`.
The model cannot write remediation. It cannot repair missing live permission,
inventory, or other evidence by assertion.

## Generation gaps

Generation adds three closed gap IDs to the report schema:

| ID | Meaning |
|---|---|
| `MODEL_OUTPUT_INVALID` | No trusted IR could be decoded |
| `MODEL_PROVIDER_FAILED` | The provider failed throughout the bounded run |
| `MODEL_REPAIR_EXHAUSTED` | Schema or semantic repairs reached the configured maximum |

These IDs are separate from the deterministic preflight IDs covered by the
40-case no-model corpus.

## Compile eligibility

`DecodeResult.ready_to_compile` is true only when:

- an immutable `PlaybookIR` exists; and
- its `GapReport` has no blocker.

A valid IR may still be returned with `ready_to_compile=false` so the UI can
show evidence gaps without trusting or compiling the model's raw text. Import
and Run must never infer eligibility independently.

## Verification

```bash
python3 soar_playbook_builder/eval/harness.py --suite model_boundary
python3 -m pytest -q tests/test_llm_provider.py tests/test_llm_decode.py
```

The scripted suite proves invalid JSON repair, hallucination rejection, raw
output non-disclosure, provider failure sanitization, bounded exhaustion, and
authoritative provenance without requiring a model endpoint.

## Deferred evidence

The offline suite does not prove:

- which real runtime implements either constraint extension correctly;
- weakest-supported model accuracy;
- GPU out-of-memory and load-shedding behavior;
- real certificate/authentication deployment;
- zero-egress behavior under packet capture; or
- live SOAR compatibility of artifacts generated from model-created IR.

Those claims stay unqualified until endpoint and SOAR test evidence is captured.
