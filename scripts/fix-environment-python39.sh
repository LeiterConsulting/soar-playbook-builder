#!/usr/bin/env bash
# Fix all Python 2.7 playbooks: SSH phenv on SOAR host + REST cleanup (works on SOAR 6.x).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/scripts/env.e2e.local"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE"

export SOAR_URL="${SOAR_URL:-https://10.236.39.108:8443}"
export SOAR_USER="${SOAR_USER:-soar_local_admin}"
export SOAR_PASSWORD="${SOAR_PASSWORD:-${SOAR_PASS:-}}"
export SOAR_VERIFY_SSL="${SOAR_VERIFY_SSL:-false}"
export SOAR_HOST="${SOAR_HOST:-10.236.39.108}"
export SSH_USER="${SSH_USER:-splunker}"
export SSH_KEY="${SSH_KEY:-${HOME}/Downloads/tylerkeypair.pem}"

if [[ -z "$SOAR_PASSWORD" ]]; then
  echo "Set SOAR_PASSWORD in scripts/env.e2e.local" >&2
  exit 1
fi

python3 "${ROOT}/scripts/fix_environment_python39_ssh.py" "$@"
