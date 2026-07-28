#!/usr/bin/env bash
# Run production E2E validation for SOAR Playbook Builder.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
ENV_FILE="${E2E_ENV:-}"

for candidate in \
  "$ENV_FILE" \
  "$ROOT/scripts/env.e2e.local" \
  "$REPO_ROOT/.env" \
  "$REPO_ROOT/.env.secrets"; do
  if [[ -n "$candidate" && -f "$candidate" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$candidate"
    set +a
    echo "Loaded env from $candidate"
    break
  fi
done

MODE="${1:-auto}"
shift || true

ARGS=(--mode "$MODE" --report-dir dist/e2e)
if [[ "${SKIP_IMPORT:-}" == "1" ]]; then
  ARGS+=(--skip-import)
fi
if [[ "${KEEP_E2E_PLAYBOOK:-}" == "1" ]]; then
  ARGS+=(--no-cleanup)
fi
if (($#)); then
  ARGS+=("$@")
fi

cd "$ROOT"
mkdir -p dist/e2e

if command -v uv >/dev/null 2>&1; then
  uv run --with httpx python scripts/e2e_validate.py "${ARGS[@]}"
else
  python3 scripts/e2e_validate.py "${ARGS[@]}"
fi

EXIT=$?
HTML="$ROOT/dist/e2e/e2e-report.html"
if [[ -f "$HTML" ]]; then
  echo ""
  echo "Open report: file://$HTML"
  if [[ "$(uname)" == "Darwin" ]]; then
    open "$HTML" 2>/dev/null || true
  fi
fi
exit $EXIT
