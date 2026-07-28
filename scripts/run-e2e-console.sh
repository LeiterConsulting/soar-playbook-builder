#!/usr/bin/env bash
# Start E2E validation console: Python API + React UI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
PORT="${E2E_CONSOLE_PORT:-8765}"
UI_PORT="${E2E_UI_PORT:-5174}"

for candidate in \
  "${E2E_ENV:-}" \
  "$ROOT/scripts/env.e2e.local" \
  "$REPO_ROOT/.env" \
  "$REPO_ROOT/.env.secrets"; do
  if [[ -n "$candidate" && -f "$candidate" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$candidate"
    set +a
    echo "Loaded env from $candidate"
  fi
done

# Fall back to sidecar dev creds when E2E file still has placeholders
SIDECAR_ENV="$ROOT/sidecar-ui/.env.local"
if [[ -f "$SIDECAR_ENV" ]]; then
  if [[ -z "${SOAR_URL:-}" ]] || [[ "$SOAR_URL" == *your-soar.example.com* ]]; then
    # shellcheck disable=SC1090
    source "$SIDECAR_ENV"
    SOAR_URL="${VITE_SOAR_URL:-$SOAR_URL}"
    SOAR_USER="${VITE_SOAR_USER:-$SOAR_USER}"
    SOAR_PASSWORD="${VITE_SOAR_PASS:-$SOAR_PASSWORD}"
    export SOAR_URL SOAR_USER SOAR_PASSWORD
    echo "Applied SOAR creds from sidecar-ui/.env.local"
  fi
fi

cleanup() {
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting E2E API on :${PORT}..."
cd "$ROOT"
if command -v uv >/dev/null 2>&1; then
  uv run --with httpx --with starlette --with uvicorn python scripts/e2e_server.py &
else
  python3 scripts/e2e_server.py &
fi
API_PID=$!

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    echo "API ready"
    break
  fi
  sleep 0.5
done

echo "Starting UI on http://127.0.0.1:${UI_PORT} ..."
cd "$ROOT/validation-console"
if [[ ! -d node_modules ]]; then
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
fi
npm run dev -- --host 127.0.0.1 --port "$UI_PORT"
