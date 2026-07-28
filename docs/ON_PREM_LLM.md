# On-prem and private model deployment

This guide describes the hardened target for natural-language generation. The
trusted path is:

```text
request + local capability evidence
        |
        v
OpenAI-compatible local endpoint
        |
        v
strict JSON decode -> Playbook IR -> deterministic preflight -> compiler
```

The model never supplies Python, shell, tools, remediation text, permission
evidence, or an import decision.

## Current status

The repository now contains the offline provider boundary, strict decoder,
bounded repair loop, deterministic preflight, and compiler. They pass scripted
adversarial tests without a live model or SOAR instance.

They are not yet connected to the installed app's Build/Import flow. The
existing MCP bridge can return model-authored Python `source`; that is a legacy
experimental path and is not part of the trusted compiler. Keep Mode B disabled
for production until the UI and REST routes accept only trusted IR results.

Live qualifications still required:

- a selected local model/runtime must pass the constrained-output corpus;
- endpoint TLS, authentication, timeout, and resource behavior must pass on the
  intended deployment host;
- the resulting compiler artifacts must pass a supported live SOAR runtime;
- no Import or Run control may accept legacy bridge-authored Python.

See [MODEL_BOUNDARY.md](./MODEL_BOUNDARY.md) for the exact software contract.

## Endpoint contract

The built-in provider uses one narrow OpenAI-compatible endpoint:

```text
POST <base_url>/chat/completions
```

The configured `base_url` must end in `/v1`. The provider can send:

- strict `response_format.type=json_schema` when the selected backend proves
  support;
- a top-level GBNF `grammar` field when the selected backend proves support; or
- unconstrained JSON text only under the explicit
  `allow_unconstrained_json=True` lab flag, followed by the same strict decoder
  and preflight.

`probe()` does not infer support from a successful HTTP status. It requires the
backend to produce the exact constrained empty object before recording schema or
grammar support. Capability claims are therefore backend/model/configuration
specific and must be re-probed after changes.

Production generation fails closed with `CONSTRAINT_UNAVAILABLE` when neither
constraint is proven.

## Network and certificate policy

Defaults are deliberately strict:

- HTTPS is required.
- TLS certificates and hostnames are verified.
- redirects and environment proxies are disabled;
- embedded credentials, URL query strings, fragments, relative path segments,
  metadata endpoints, link-local, reserved, multicast, and unspecified
  addresses are blocked;
- loopback requires `allow_loopback=True`;
- plain HTTP requires the separate `allow_insecure_http=True` lab override;
- disabled TLS verification requires the separate
  `allow_insecure_tls=True` lab override;
- request, message, response, and timeout limits are bounded;
- custom CA bundles must be existing absolute files; and
- provider errors contain stable codes, not response bodies or secrets.

The lab overrides are independent. Allowing local HTTP never silently permits
unverified HTTPS.

For access from another workstation, bind the model runtime to the private LAN
only, restrict its port in the host firewall to the builder/SOAR hosts, and put
authentication plus TLS termination in front of it. Do not expose an
unauthenticated `0.0.0.0` listener to the internet.

## Example provider configuration

This is a library-level example; it does not enable the app UI:

```python
from llm import (
    GenerationContext,
    OpenAICompatibleProvider,
    ProviderConfig,
    generate_ir,
)

config = ProviderConfig(
    base_url="https://llm.internal.example/v1",
    model="organization-qualified-model",
    auth_value="Bearer <token-from-secret-store>",
    ca_bundle="/etc/pki/ca-trust/source/anchors/internal-ca.pem",
)

capabilities = OpenAICompatibleProvider(config).probe()
provider = OpenAICompatibleProvider(config, capabilities=capabilities)

result = generate_ir(
    provider,
    "Enrich the artifact IP and route failures to a neutral end node.",
    capability_index,
    context=GenerationContext(
        operating_mode="air_gapped",
        model="organization-qualified-model",
        prompt_version="ir-generate-v1",
        generated_at="2026-07-28T16:00:00+00:00",
        evaluated_at="2026-07-28T16:00:00+00:00",
    ),
)
```

Tokens belong in a secret store on the endpoint/bridge host. They must not be
committed, placed in IR, returned to the browser, or exported with SOAR asset
configuration.

## Choosing a runtime for the available workstation

For a single powerful GPU workstation, start with the runtime that can reliably
enforce the emitted JSON Schema or GBNF and expose a private OpenAI-compatible
API. Operational simplicity matters more than maximum throughput during
qualification.

- A llama.cpp-compatible server is attractive for the first gate because the
  repository emits and externally validates GBNF.
- Ollama is convenient for local model and lifecycle experiments, but its exact
  constrained-output behavior must be probed and tested rather than assumed.
- vLLM is a strong candidate when Linux/CUDA serving throughput, batching, and
  multi-client operation become priorities.
- A gateway adds routing and policy features but also adds another dependency,
  configuration surface, and failure boundary. Do not add one until it solves a
  demonstrated requirement.

Runtime and model support are evidence-based. A model is not supported merely
because it starts or returns plausible JSON.

## Offline qualification

Run the deterministic boundary tests:

```bash
python3 soar_playbook_builder/eval/harness.py --suite model_boundary
python3 -m pytest -q tests/test_llm_provider.py tests/test_llm_decode.py
```

Then qualify the real endpoint with network capture or a deny-by-default egress
policy:

1. record provider/runtime/model version and model-file digest;
2. probe schema and grammar support;
3. run the fixed generation corpus at the bounded attempt count;
4. prove invalid JSON, duplicate keys, executable fields, hallucinated
   capabilities, timeout, oversize response, and repair exhaustion all block;
5. confirm raw model text and credentials never appear in reports or browser
   responses; and
6. publish the exact pass rate instead of a generic “AI works” claim.

## Success criteria

A local model configuration is eligible for the app only when:

- every accepted output parses as IR 1.0.0;
- zero model-authored Python reaches compiler, import, or execution;
- every accepted action, parameter, output, asset, and datapath survives
  deterministic preflight;
- repair stops within the configured maximum;
- provider and validation failures return closed `GapReport` IDs;
- the test run demonstrates zero unintended internet egress; and
- the model/runtime/version/digest tuple is recorded as the qualified target.
