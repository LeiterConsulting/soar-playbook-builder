#!/usr/bin/env bash
# Run ON the SOAR host (SSH) to check whether playbooks_to_py3 is available.
set -euo pipefail

PHANTOM_HOME="${PHANTOM_HOME:-/opt/phantom}"
PHENV="${PHENV:-${PHANTOM_HOME}/bin/phenv}"

echo "=== SOAR home ==="
echo "${PHANTOM_HOME}"

echo ""
echo "=== playbooks_to_py3 on disk ==="
sudo find "${PHANTOM_HOME}" -name 'playbooks_to_py3*' -type f 2>/dev/null | head -20 || true

echo ""
echo "=== phenv playbooks_to_py3 -h (correct; do NOT use phenv --help) ==="
if [[ -x "${PHENV}" ]]; then
  sudo -u phantom "${PHENV}" playbooks_to_py3 -h 2>&1 | head -25 || true
else
  echo "missing: ${PHENV}"
fi

echo ""
echo "=== If 'not found' above ==="
echo "playbooks_to_py3 is not on this SOAR build (common on 8.x)."
echo "Use Playbook Builder re-import (Python 3.13 metadata) or SOAR UI:"
echo "  Playbooks -> Python update required -> Convert to Python 3.13"
