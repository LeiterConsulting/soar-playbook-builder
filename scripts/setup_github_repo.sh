#!/usr/bin/env bash
# One-time: init THIS repo and point origin at LeiterConsulting/soar-playbook-builder.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
GITHUB_USER="${GITHUB_USER:-LeiterConsulting}"
REPO_NAME="${REPO_NAME:-soar-playbook-builder}"

cd "${REPO_DIR}"

if git -C "${REPO_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if remote="$(git remote get-url origin 2>/dev/null || true)"; then
    if [[ "${remote}" == *deslicer/mcp-for-splunk* ]]; then
      echo "ERROR: origin still points at deslicer/mcp-for-splunk." >&2
      echo "Run from ~/soar-playbook-builder only — not mcp-for-splunk/packaging/..." >&2
      git remote remove origin
    fi
  fi
else
  rm -rf .git
  git init
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
  echo "Added origin: git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
fi

echo ""
echo "Next steps:"
echo "  1. Create empty repo: https://github.com/new → ${GITHUB_USER}/${REPO_NAME}"
echo "  2. git add -A && git commit -m 'Release: SOAR Playbook Builder <manifest version>'"
echo "  3. git branch -M main"
echo "  4. git push -u origin main"
echo ""
echo "Use SSH (recommended) or HTTPS with a Personal Access Token — not your GitHub password."
