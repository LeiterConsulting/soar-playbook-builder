#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/scripts/env.e2e.local"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"
export SOAR_URL="${SOAR_URL:-https://10.236.39.108:8443}"
export SOAR_USER="${SOAR_USER:-soar_local_admin}"
export SOAR_PASSWORD="${SOAR_PASSWORD:-${SOAR_PASS:-}}"
export SOAR_VERIFY_SSL="${SOAR_VERIFY_SSL:-false}"
python3 "${ROOT}/scripts/diagnose_playbook_python.py"
