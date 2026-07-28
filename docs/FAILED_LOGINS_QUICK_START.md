# Failed logins quick start — Okta response playbook

15-minute lab path without ES–SOAR export or LLM.

## Prerequisites

- Playbook Builder app **v2.10.0+** installed on SOAR
- Okta app installed on SOAR with asset (e.g. `okta`)
- Playbook Builder asset `asset_defaults`: `{"okta": "okta"}`

## Steps

### 1. Open Playbook Builder

Apps → Playbook Builder → open sidecar URL (`.../chat`).

Status pill **Templates only** is expected in air-gapped environments.

### 2. Generate playbook

**Guided wizard** → **Excessive Failed Logins → Start**

Or: Pattern library → **Excessive Failed Logins (Okta)** → **Use template**

Preview should show: Collect → get user → decision → clear sessions / disable user.

### 3. Preflight and import

- If integration panel appears: map **Okta** to your asset → confirm
- Click **Import** → wait for **✓ Synced**
- Click **Open in SOAR** → Visual Editor

### 4. Manual test container (no ES export)

Until ES–SOAR pairing is configured:

1. SOAR → **Incidents** → **Create container**
2. Add artifact type **user** with CEF field `user` = test username (e.g. lab account)
3. Set container **severity** = `high` (for remediation path)
4. **Playbooks** tab → run **excessive_failed_logins** (or imported name)
5. Verify Okta actions in action results; note on container for low-severity path

### 5. ES integration (when approved)

1. ES → Configure → Incident Review → Splunk SOAR Integration
2. Pair SOAR; configure notable export
3. Match playbook label `excessive_failed_logins` or container routing rules

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Okta preflight missing | Create Okta asset; set asset_defaults |
| get user failed | Container needs `cef.user` artifact |
| Invalid datapath in VPE | Delete playbook; re-import v2.10.0+ |
| ES Response tab empty | Use manual container until ES–SOAR wired |

Use sidecar **Troubleshooting guide** for step-by-step fixes.

## What this playbook does

| Severity | Actions |
|----------|---------|
| high / critical | Okta get user → clear sessions → disable user → note |
| other | Okta get user → informational note |
| Okta failure | Assign tier2 |

Username is collected from `artifact:*.cef.user` or `artifact:*.cef.destinationUserName`.
