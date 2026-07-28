#!/usr/bin/env bash
# Convert Python 2.7 classic playbooks on the SOAR appliance (required on SOAR 6.x).
#
# REST re-import cannot change python_version on classic playbooks — Splunk requires phenv.
# See: https://help.splunk.com/.../convert-playbooks-or-custom-functions-from-python-2-to-python-3
#
# Usage:
#   ./scripts/convert_playbooks_py3_ssh.sh servicenow_p1_incident hello_world
#
# After conversion you get <slug>_py3 (Python 3). Delete the old 2.7 copy in Playbooks UI.

set -euo pipefail

SOAR_HOST="${SOAR_HOST:-10.236.39.108}"
SSH_USER="${SSH_USER:-splunker}"
SSH_KEY="${SSH_KEY:-${HOME}/Downloads/tylerkeypair.pem}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <playbook_slug> [more_slugs...]" >&2
  echo "Example: $0 servicenow_p1_incident hello_world" >&2
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [[ -f "$SSH_KEY" ]]; then
  SSH_OPTS+=(-i "$SSH_KEY")
fi

for slug in "$@"; do
    echo "==> phenv playbooks_to_py3 local/${slug} local (on ${SOAR_HOST})..."
  ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SOAR_HOST}" \
    "sudo -u phantom /opt/phantom/bin/phenv playbooks_to_py3 local/${slug} local"
  echo ""
  echo "    Created: ${slug}_py3  (Python 3)"
  echo "    Next:    Playbooks -> delete old '${slug}' (Python 2.7)"
  echo "    Optional: rename ${slug}_py3 -> ${slug} in Playbooks if you need the original name"
  echo ""
done

echo "Verify: ./scripts/run-diagnose-python.sh  (or diagnose_playbook_python.py)"
