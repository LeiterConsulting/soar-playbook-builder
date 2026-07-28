# Trusted IR review-only path

The repository now exposes the IR/compiler/preflight pipeline separately from
the legacy Python scaffold/import path. This is an integration checkpoint, not
an import feature.

## API actions

All actions use the existing authenticated same-origin `/chat` handler.

| Action | Method | Purpose |
|---|---|---|
| `list_ir_templates` | GET | List or BM25-filter canonical shipped IR templates |
| `trusted_retrieve` | GET | Return bounded local action/template candidates |
| `trusted_ir_template_review` | POST | Rebind and review one shipped or strict organization canonical template |
| `trusted_ir_review` | POST | Strictly review a caller-supplied IR object |

The review actions:

1. load a persisted capability index or a fail-closed unverified baseline;
2. overwrite index/mode/time provenance with server-owned values;
3. optionally bind exact action-node IDs to named assets;
4. parse the closed IR contract;
5. run deterministic preflight;
6. compile preview-only Python and visual siblings;
7. return IR, report, compiler version, and artifact hashes; and
8. always return `review_only=true`, `import_enabled=false`,
   `ready_for_import=false`, and `TRUSTED_IMPORT_DISABLED`.

No review response exposes a top-level legacy `source` field, so the existing
draft importer cannot consume it accidentally.

Organization templates in `custom_ir_templates_json` use the same review
service. Both their wrapper ID and IR `metadata.template_id`/`id` must match.
Legacy Python organization templates are ignored by default and cannot enter
this review path even when the lab-only compatibility switch is enabled.

## Example

```json
{
  "action": "trusted_ir_template_review",
  "template_id": "hello",
  "operating_mode": "air_gapped",
  "asset_bindings": {}
}
```

An action template with no live evidence remains blocked. The Hello template
can produce `gap_report.status=ok` offline, but Import remains locked because
native VPE/runtime and authorization evidence are still absent.

## UI

The template library contains a separate **Trusted IR preview** card. It shows:

- IR-valid state;
- exact preflight status and gap IDs;
- an explicit Import-locked badge;
- IR, review, Python-preview, and visual-preview hashes; and
- `unverified_without_live_soar` native visual-schema status.

It does not enable or repurpose the legacy Import/Run controls.

## Verification

```bash
python3 -m pytest -q tests/test_trusted_review.py
cd sidecar-ui && npm run build
```

The mock browser flow verifies both a clean Hello review and a blocked action
review while Import and Run remain disabled.

## Remaining integration gates

Trusted import must not be enabled until:

- any remaining built-in/legacy organization migration is complete;
- review approval binds to an authenticated SOAR principal and immutable
  `review_id`;
- the same IR/report/hash is checked again at commit time;
- import is idempotent and isolated per user/session;
- native visual JSON is live-qualified on supported SOAR versions; and
- authorization, audit, rollback, and runtime tests pass on the live instance.
