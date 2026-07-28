#!/usr/bin/env bash
# Re-import Playbook Builder playbooks on Python 3.9 (dry-run by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/scripts/env.e2e.local"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

SOAR_URL="${SOAR_URL:-https://10.236.39.108:8443}"
SOAR_USER="${SOAR_USER:-soar_local_admin}"
SOAR_PASSWORD="${SOAR_PASSWORD:-${SOAR_PASS:-}}"

if [[ -z "$SOAR_PASSWORD" ]]; then
  echo "Set SOAR_PASSWORD or SOAR_PASS (scripts/env.e2e.local)." >&2
  exit 1
fi

export SOAR_URL SOAR_USER SOAR_PASSWORD SOAR_VERIFY_SSL="${SOAR_VERIFY_SSL:-false}"

python3 "${ROOT}/scripts/migrate_playbooks_python39.py" "$@"
