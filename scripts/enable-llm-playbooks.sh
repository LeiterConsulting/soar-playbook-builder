#!/usr/bin/env bash
# Enable LLM playbook generation: OpenAI key OR on-prem LLM (OPENAI_BASE_URL) → MCP restart → SSH tunnel → verify.
# On-prem LLM guide: docs/ON_PREM_LLM.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
SECRETS_FILE="${ROOT}/.env.secrets"
KEY_FILE="${HOME}/.openai_playbook_builder_key"

SOAR_HOST="${SOAR_HOST:-10.236.39.108}"
SOAR_USER="${SOAR_USER:-splunker}"
SSH_KEY="${SSH_KEY:-${HOME}/Downloads/tylerkeypair.pem}"
SOAR_API_USER="${SOAR_API_USER:-soar_local_admin}"
SOAR_API_PASS="${SOAR_API_PASS:-password}"
SOAR_URL="${SOAR_URL:-https://${SOAR_HOST}:8443}"
MCP_PORT="${MCP_SERVER_PORT:-8003}"
TUNNEL_LOG="${TMPDIR:-/tmp}/playbook-builder-tunnel.log"
MCP_LOG="${TMPDIR:-/tmp}/playbook-builder-mcp.log"

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
grn() { printf '\033[0;32m%s\033[0m\n' "$*"; }
ylw() { printf '\033[1;33m%s\033[0m\n' "$*"; }

resolve_openai_key() {
  if [[ -n "${1:-}" ]]; then
    echo "$1"
    return
  fi
  if [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "your_openai_api_key_here" ]]; then
    echo "$OPENAI_API_KEY"
    return
  fi
  if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$SECRETS_FILE"; set +a
    if [[ -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "your_openai_api_key_here" ]]; then
      echo "$OPENAI_API_KEY"
      return
    fi
  fi
  if [[ -f "$KEY_FILE" ]]; then
    tr -d '[:space:]' < "$KEY_FILE"
    return
  fi
  return 1
}

write_env_key() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    red "Missing $ENV_FILE — run from mcp-for-splunk repo with .env present."
    exit 1
  fi
  if grep -q '^OPENAI_API_KEY=' "$ENV_FILE"; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${key}|" "$ENV_FILE"
    else
      sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${key}|" "$ENV_FILE"
    fi
  else
    printf '\nOPENAI_API_KEY=%s\n' "$key" >> "$ENV_FILE"
  fi
  if ! grep -q '^AGENT_BRIDGE_MODEL=' "$ENV_FILE"; then
    printf 'AGENT_BRIDGE_MODEL=gpt-4o-mini\n' >> "$ENV_FILE"
  fi
  grn "Updated OPENAI_API_KEY in $ENV_FILE"
}

stop_mcp() {
  cd "$ROOT" 2>/dev/null || return 0
  ylw "Stopping any existing MCP on :${MCP_PORT}..."
  if [[ -f .mcp_local_server.pid ]]; then
    kill "$(cat .mcp_local_server.pid)" 2>/dev/null || true
    rm -f .mcp_local_server.pid
  fi
  pkill -f "src/server.py --transport http" 2>/dev/null || true
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti :"${MCP_PORT}" 2>/dev/null | xargs kill -9 2>/dev/null || true
  fi
  sleep 1
}

wait_for_mcp_health() {
  local attempt=0
  local max_attempts=45
  ylw "Waiting for MCP health (Splunk retries + plugin load can take 20–40s)..."
  while [[ "$attempt" -lt "$max_attempts" ]]; do
    if curl -sf "http://127.0.0.1:${MCP_PORT}/agent/health" >/dev/null 2>&1; then
      grn "MCP health OK"
      return 0
    fi
    attempt=$((attempt + 1))
    if (( attempt == 1 || attempt % 3 == 0 )); then
      ylw "  … still starting (${attempt}/${max_attempts})"
    fi
    sleep 2
  done
  red "MCP health failed after $((max_attempts * 2))s"
  red "  server log: $ROOT/logs/mcp_splunk_server.log"
  tail -20 "$ROOT/logs/mcp_splunk_server.log" 2>/dev/null || true
  exit 1
}

start_mcp() {
  ylw "Starting MCP on port ${MCP_PORT}..."
  cd "$ROOT"
  mkdir -p logs
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
  fi
  set +a
  export NO_PROXY="${NO_PROXY:-},api.openai.com,openai.com"
  export MCP_STATELESS_HTTP=true
  export MCP_JSON_RESPONSE=true
  # Direct server start — avoids mcp-server CLI banner, uv sync, and MCP Inspector hang
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    nohup uv run python src/server.py --transport http --host 0.0.0.0 --port "${MCP_PORT}" \
    >>"$ROOT/logs/mcp_splunk_server.log" 2>&1 &
  echo $! > .mcp_local_server.pid
  ylw "Server PID $(cat .mcp_local_server.pid) — log: logs/mcp_splunk_server.log"
  wait_for_mcp_health
}

start_tunnel() {
  if [[ ! -f "$SSH_KEY" ]]; then
    red "SSH key not found: $SSH_KEY"
    exit 1
  fi
  chmod 400 "$SSH_KEY" 2>/dev/null || true
  if pgrep -f "ssh.*-R ${MCP_PORT}:127.0.0.1:${MCP_PORT}.*${SOAR_HOST}" >/dev/null 2>&1; then
    grn "SSH tunnel already running"
    return
  fi
  ylw "Starting SSH reverse tunnel to ${SOAR_HOST}..."
  nohup ssh -i "$SSH_KEY" -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
    -N -R "${MCP_PORT}:127.0.0.1:${MCP_PORT}" "${SOAR_USER}@${SOAR_HOST}" \
    >"$TUNNEL_LOG" 2>&1 &
  sleep 2
  grn "Tunnel started (log: $TUNNEL_LOG)"
}

verify_soar_tunnel() {
  ylw "Verifying MCP reachable from SOAR host..."
  if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "${SOAR_USER}@${SOAR_HOST}" \
    "curl -sf http://127.0.0.1:${MCP_PORT}/agent/health" >/dev/null 2>&1; then
    grn "SOAR → MCP tunnel OK"
    return
  fi
  ylw "Could not verify tunnel from this host — start manually if sidecar shows bridge down:"
  ylw "  ssh -i $SSH_KEY -N -R ${MCP_PORT}:127.0.0.1:${MCP_PORT} ${SOAR_USER}@${SOAR_HOST}"
}

install_soar_app() {
  local tgz="${PKG}/dist/soar_playbook_builder.tgz"
  if [[ ! -f "$tgz" ]]; then
    ylw "Building SOAR app package..."
    (cd "$PKG" && ./package_app.sh)
  fi
  ylw "Uploading app to SOAR..."
  scp -i "$SSH_KEY" -o ConnectTimeout=15 "$tgz" "${SOAR_USER}@${SOAR_HOST}:/tmp/soar_playbook_builder.tgz"
  ssh -i "$SSH_KEY" "${SOAR_USER}@${SOAR_HOST}" bash -s <<'REMOTE'
set -e
TGZ=/tmp/soar_playbook_builder.tgz
if command -v phantom-cli >/dev/null 2>&1; then
  sudo phantom-cli install-app "$TGZ" || phantom-cli install-app "$TGZ"
elif [[ -d /opt/phantom/app/install ]]; then
  sudo cp "$TGZ" /opt/phantom/app/install/ && echo "Copied to install dir — check SOAR Apps UI"
else
  echo "Manual install: Apps → Install App → $TGZ on SOAR UI"
fi
REMOTE
  grn "SOAR app upload complete (confirm in Apps UI if not auto-installed)"
}

test_llm_build() {
  local msg='Build a playbook that looks up the sender domain in WHOIS, adds a note with registrant info, and assigns the container to tier2 if the domain was registered in the last 30 days.'
  local tmp
  tmp="$(mktemp /tmp/playbook-builder-chat.XXXXXX.json)"
  ylw "Testing novel NL build via MCP chat..."
  local http_code
  http_code=$(curl -s -o "$tmp" -w "%{http_code}" -X POST "http://127.0.0.1:${MCP_PORT}/agent/api/chat" \
    -H 'Content-Type: application/json' \
    -d "{\"message\":$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$msg"),\"context\":{}}")
  if [[ "$http_code" != "200" ]]; then
    red "Chat API HTTP $http_code"
    head -c 400 "$tmp" 2>/dev/null || true
    echo
    rm -f "$tmp"
    exit 1
  fi
  python3 - "$tmp" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    d = json.load(fh)
ok = bool(d.get("source") and "def on_start" in d.get("source", ""))
pat = d.get("pattern", "")
print("pattern:", pat)
print("has_source:", ok)
print("preview_blocks:", len(d.get("preview") or []))
if not ok:
    print("content:", (d.get("content") or d.get("error") or "")[:300])
    sys.exit(1)
if pat == "nl-generated":
    print("LLM generation confirmed (nl-generated)")
elif pat:
    print("Pattern scaffold used:", pat)
PY
  rm -f "$tmp"
  grn "Chat API returned playbook source"
}

print_sidecar_url() {
  SOAR_URL="$SOAR_URL" SOAR_USER="$SOAR_API_USER" SOAR_PASS="$SOAR_API_PASS" \
    "${PKG}/scripts/print_sidecar_url.sh" || true
}

main() {
  local key=""
  key="$(resolve_openai_key "${1:-}" 2>/dev/null || true)"
  if [[ -n "$key" ]]; then
    write_env_key "$key"
  else
    ylw "No OpenAI API key found — MCP will use pattern matching only."
    ylw "Add key: $0 sk-...  OR  echo sk-... > $KEY_FILE  OR  OPENAI_API_KEY=sk-... in $SECRETS_FILE"
  fi

  stop_mcp
  start_mcp
  start_tunnel
  verify_soar_tunnel
  install_soar_app
  test_llm_build
  print_sidecar_url
  grn "Done. Open the sidecar URL and send a novel playbook prompt."
}

main "${1:-}"
