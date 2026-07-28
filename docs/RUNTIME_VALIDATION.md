# Runtime validation (all templates)

Automated vetting for every Playbook Builder template: **structural** (offline, no SOAR) and **live runtime** (import + container + playbook run on your lab).

## Quick start

```bash
cd soar-playbook-builder

# Offline — all 11 templates (Python, COA, callbacks, assets, NL routing)
python3 scripts/runtime_validate.py

# Live — safe tier only (hello, ES notable, indicator, phishing)
cp scripts/env.e2e.example scripts/env.e2e.local   # edit SOAR_URL / creds
source scripts/env.e2e.local
./scripts/run-runtime-validate.sh --live --mode safe

# When MCP/LLM stack is available — same runs via mcp_soar SOARClient
./scripts/run-runtime-validate.sh --live --mode safe --transport mcp
```

Reports: `dist/runtime-vet/report.json` and `report.md`.

## Modes (tiers)

| Mode | Templates exercised live | Notes |
|------|--------------------------|-------|
| `safe` (default) | hello, es-notable-response, indicator-enrichment, phishing-enrichment | No external integrations required |
| `integration` | safe + okta-idp-response, servicenow-incident, virustotal-enrichment | Actions may fail if assets missing — `allow_action_fail` → warn |
| `destructive` | all 11 | **Requires `RUN_DESTRUCTIVE=1`** — may disable users, block IPs, quarantine |

Structural checks always run regardless of mode.

## Transport

| Transport | When to use |
|-----------|-------------|
| `rest` (default) | Air-gapped lab — direct SOAR REST from your workstation |
| `mcp` | After LLM/MCP approval — validates `mcp_soar` client path (same REST endpoints) |

MCP transport needs `mcp-for-splunk` repo on `PYTHONPATH` (sibling of `packaging/`). Sidecar NL/MCP bridge is unchanged; this only affects how **playbook_run** is invoked.

## Per-template fixtures

Fixtures live in `soar_playbook_builder/runtime_fixtures.py` — container severity, seed artifacts, expected notes/actions.

## Dependencies

```bash
pip install httpx   # or: python3 -m venv .venv && .venv/bin/pip install httpx
```

## CI / release gate

```bash
python3 tests/test_all_patterns.py      # pytest-style structural vet
python3 tests/test_runtime_fixtures.py  # fixture coverage
python3 scripts/runtime_validate.py     # full structural report
```

Before customer sign-off, run live safe tier against the target SOAR instance and archive `dist/runtime-vet/report.md`.

## Related

- [E2E_VALIDATION.md](./E2E_VALIDATION.md) — sidecar import + MCP bridge phases
- [AIR_GAPPED_OPERATIONS.md](./AIR_GAPPED_OPERATIONS.md) — Mode A templates without LLM
