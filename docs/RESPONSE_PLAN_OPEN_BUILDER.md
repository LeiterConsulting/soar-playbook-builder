# Response plan: auto-run Open Playbook Builder on ES export

When Splunk ES exports a notable to SOAR, this response plan runs the **Open Playbook Builder** utility playbook automatically. The playbook adds a case note with the sidecar URL (`container_id` + ES `event_id` / `rule_name`).

## Prerequisites

1. App **v2.14.1+** and `dist/open_playbook_builder.tgz` imported
2. `BUILDER_ASSET` in the utility playbook matches your Playbook Builder asset name
3. ES → SOAR export enabled (label e.g. `es_notable_response`)

## Manual setup (recommended)

1. **SOAR → Administration → Response Plans → Add**
2. **Name:** `ES Notable — Open Playbook Builder`
3. **Trigger:** Container created
4. **Condition:** Label **contains** `es_notable_response`  
   (Change to match your ES export label if different.)
5. **Action:** Run playbook → **Open Playbook Builder**
6. **Run mode:** Automatic
7. Save and enable

## Verify

1. Trigger or export a test notable from ES
2. Open the new SOAR case
3. Confirm a note **Playbook Builder** with a sidecar URL
4. Open the URL → header shows **Case …** and (if configured) **Back to Mission Control**

## Template

See `soar_content/response_plan_open_playbook_builder.json` for a machine-readable template and ES export checklist.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Plan never fires | Label on new cases must match condition; check ES export mapping |
| Playbook fails | Set `BUILDER_ASSET` in `utility_playbooks/open_playbook_builder.py` and re-import |
| No URL in note | Run **get sidecar url** manually on the asset to test connectivity |
