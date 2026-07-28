#!/usr/bin/env bash
# Vet all playbook templates — structural + optional live SOAR runtime.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${DIR}/.." && pwd)"

if [[ -f "${DIR}/env.e2e.local" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "${DIR}/env.e2e.local"
  set +a
fi

cd "${ROOT}"
python3 "${DIR}/runtime_validate.py" "$@"
