#!/bin/bash
# Wrapper: phenv playbooks_to_py3 must run as user phantom on SOAR.
# Usage: phenv_upgrade.sh <repo/playbook> [output_repo]
set -euo pipefail

PLAYBOOK_PATH="${1:?repo/playbook required}"
OUTPUT_REPO="${2:-local}"
PHANTOM_HOME="${PHANTOM_HOME:-/opt/phantom}"
PHENV="${PHENV_PATH:-${PHANTOM_HOME}/bin/phenv}"

run_as_phantom() {
  TOOL=""
  for candidate in \
    "${PHANTOM_HOME}/bin/playbooks_to_py3" \
    "${PHANTOM_HOME}/bin/playbooks_to_py3.py" \
    "${PHANTOM_HOME}/share/playbooks_to_py3.py"; do
    if [[ -f "$candidate" ]]; then
      TOOL="$candidate"
      break
    fi
  done

  run_phenv() {
    if [[ "$(id -un)" == "phantom" ]]; then
      "$PHENV" playbooks_to_py3 "$PLAYBOOK_PATH" "$OUTPUT_REPO"
    else
      sudo -n -u phantom "$PHENV" playbooks_to_py3 "$PLAYBOOK_PATH" "$OUTPUT_REPO"
    fi
  }

  run_direct() {
    local py="${PHANTOM_HOME}/usr/python313/bin/python3.13"
    if [[ -x "$py" ]]; then
      if [[ "$(id -un)" == "phantom" ]]; then
        "$py" "$TOOL" "$PLAYBOOK_PATH" "$OUTPUT_REPO"
      else
        sudo -n -u phantom "$py" "$TOOL" "$PLAYBOOK_PATH" "$OUTPUT_REPO"
      fi
    elif [[ -x "$TOOL" ]]; then
      if [[ "$(id -un)" == "phantom" ]]; then
        "$TOOL" "$PLAYBOOK_PATH" "$OUTPUT_REPO"
      else
        sudo -n -u phantom "$TOOL" "$PLAYBOOK_PATH" "$OUTPUT_REPO"
      fi
    else
      return 1
    fi
  }

  if [[ -n "$TOOL" ]]; then
    run_direct && return
  fi
  if [[ -x "$PHENV" ]]; then
    run_phenv && return
    sudo -n "$PHENV" playbooks_to_py3 "$PLAYBOOK_PATH" "$OUTPUT_REPO" && return
  fi
  if command -v phenv >/dev/null 2>&1; then
    sudo -n -u phantom phenv playbooks_to_py3 "$PLAYBOOK_PATH" "$OUTPUT_REPO" && return
  fi
  echo "playbooks_to_py3 not found (common on SOAR 8.x). Delete 2.7 playbook and re-import via Playbook Builder." >&2
  exit 1
}

run_as_phantom
