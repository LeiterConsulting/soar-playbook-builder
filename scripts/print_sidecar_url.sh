#!/usr/bin/env bash
# Print the correct SOAR Playbook Builder sidecar URL (handler directory from REST).
set -euo pipefail

SOAR_URL="${SOAR_URL:-https://10.236.39.108:8443}"
SOAR_USER="${SOAR_USER:-soar_local_admin}"
SOAR_PASS="${SOAR_PASS:-password}"
ASSET="${ASSET:-mcpbridge}"
PLAYBOOK_ID="${PLAYBOOK_ID:-${1:-}}"
export SOAR_URL SOAR_USER SOAR_PASS ASSET PLAYBOOK_ID

curl -sk -u "${SOAR_USER}:${SOAR_PASS}" "${SOAR_URL}/rest/app?page_size=200" -o /tmp/soar_apps.json -w "%{http_code}" > /tmp/soar_apps_http.txt || true
HTTP=$(cat /tmp/soar_apps_http.txt 2>/dev/null || echo "000")
if [[ ! -s /tmp/soar_apps.json ]] || [[ "$HTTP" != "200" ]]; then
  echo "ERROR: Could not reach SOAR or /rest/app failed (HTTP ${HTTP})." >&2
  echo "  Check VPN/SSH, SOAR_URL, and credentials." >&2
  head -c 200 /tmp/soar_apps.json 2>/dev/null >&2 || true
  exit 1
fi

python3 -c "
import json, sys, os

with open('/tmp/soar_apps.json') as f:
    raw = json.load(f)
if isinstance(raw, dict):
    apps = raw.get('data') or raw.get('apps') or []
elif isinstance(raw, list):
    apps = raw
else:
    apps = []

target = None
for a in apps:
    if not isinstance(a, dict):
        continue
    if a.get('appid') == 'a7c3e891-4f2d-4b18-9e6a-1d5f8c2b0e47':
        target = a
        break
    n = (a.get('name') or '').lower()
    pkg = (a.get('package_name') or '').lower()
    if pkg in ('soar_playbook_builder', 'phantom_playbook_builder', 'phantom_soar_tutor') or ('playbook' in n and 'builder' in n):
        target = a

if not target:
    print('ERROR: Playbook Builder app not found in /rest/app', file=sys.stderr)
    print('Hint: look for soar_playbook_builder in Apps UI', file=sys.stderr)
    sys.exit(1)

d = target.get('directory')
if not d:
    print('ERROR: app has no directory field — reinstall soar_playbook_builder.tgz', file=sys.stderr)
    sys.exit(1)

print(f\"App name: {target.get('name')}\")
print(f\"Version:  {target.get('app_version')}\")
print(f\"Directory (USE IN URL): {d}\")
base = os.environ.get('SOAR_URL', 'https://10.236.39.108:8443').rstrip('/')
asset = os.environ.get('ASSET', 'mcpbridge')
pb = os.environ.get('PLAYBOOK_ID', '')
url = f\"{base}/rest/handler/{d}/{asset}/chat\"
if pb:
    url += f\"?playbook_id={pb}\"
print(f\"Sidecar URL:\\n{url}\")
es_link = f\"{base}/rest/handler/{d}/{asset}/es_link?event_id=EVENT_ID&rule_name=RULE_NAME\"
print(f\"\\nES drilldown (es_link) — replace EVENT_ID / RULE_NAME:\\n{es_link}\")
print(f\"\\nSee docs/ES_SOAR_BUILDER_STITCH.md for ES ↔ SOAR ↔ Builder setup.\")
"
