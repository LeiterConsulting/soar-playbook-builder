# Demo data and NL environment self-healing

Playbook Builder ships **five sample cases** (9001–9005), **runtime fixtures**, and **`sample_data/sample_cases.json`** in the install bundle so you can vet playbooks without live ES notables.

See [RUN_TAB_DEMO.md](./RUN_TAB_DEMO.md) for the step-by-step Run tab smoke test.

## Sample cases vs real SOAR containers

| Source | Case IDs | Run on case |
|--------|----------|-------------|
| Sample | 9001–9005 | Metadata only until provisioned |
| SOAR (live) | REST container IDs | Ready after **Link** |
| Provisioned demo | New container ID | **Create on SOAR** from a sample row |

On the **Run** tab, pick a sample case and click **Create on SOAR**. The app calls `provision_demo_case`, creates a container + artifacts from the matching fixture, then links the real `container_id` automatically.

Sample → fixture mapping:

- 9001 → `failed-logins-okta` (destructive — lab only)
- 9002 → `phishing-enrichment` (safe — showcase)
- 9003 → `insider-threat-ad` (destructive — lab only)
- 9004 → `es-notable-response` (safe — showcase)
- 9005 → `hello` (safe — smallest smoke test)

Built-in samples work **without** setting `sample_cases_json` on the asset. Use the bundled JSON only when adding org-specific demo rows.

## Natural language when MCP is offline

The **Build** tab shows an environment banner when the MCP bridge is unreachable:

- **Use template** — scaffold the suggested pattern without LLM
- **Retry bridge** — re-probe `mcp_bridge_url` on the asset
- **Refresh checks** — run `environment_check` again

When **asset_defaults** is missing but SOAR has configured integrations (Okta, Slack, etc.), the banner shows **Fix environment**. One click discovers unambiguous asset name matches and writes `asset_defaults` onto the Playbook Builder asset — no manual JSON editing.

## API actions

| Action | Method | Purpose |
|--------|--------|---------|
| `environment_check` | GET | MCP bridge, asset defaults, demo fixtures |
| `apply_environment_fixes` | POST | Auto-map integrations → `asset_defaults` (`confirm=1` to apply) |
| `provision_demo_case` | POST | `sample_id` / `pattern_id`, `confirm=1` to create |
| `list_cases` | GET | Sample + live SOAR cases |

## Asset configuration

Set on the Playbook Builder asset:

- `mcp_bridge_url` — LLM/MCP tunnel from SOAR
- `asset_defaults` — JSON map, e.g. `{"okta":"okta","slack":"slack_lab"}`
- `sample_cases_json` — optional merge/override for demo case picker (see bundled `sample_data/sample_cases.json`)

Missing defaults are informational; import may prompt for integrations.

## In-app help

The sidecar **Help** tab includes **Demo Data & Run Lab Testing** and **Natural Language Testing & Recovery Loop** (same content as [NL_TESTING_AND_RECOVERY.md](./NL_TESTING_AND_RECOVERY.md)).
