#!/usr/bin/env bash
# Diagnose Playbook Builder sidecar 500 / empty preview (SOAR handler + MCP tunnel).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${PKG}/scripts/env.e2e.local"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

SOAR_URL="${SOAR_URL:-https://10.236.39.108:8443}"
SOAR_USER="${SOAR_USER:-soar_local_admin}"
SOAR_PASSWORD="${SOAR_PASSWORD:-${SOAR_PASS:-password}}"
PB_ASSET="${PB_ASSET:-mcpbridge}"
MCP_PORT="${MCP_SERVER_PORT:-8003}"

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
grn() { printf '\033[0;32m%s\033[0m\n' "$*"; }
ylw() { printf '\033[1;33m%s\033[0m\n' "$*"; }

ylw "=== 1) MCP on Mac (localhost:${MCP_PORT}) ==="
if curl -sf "http://127.0.0.1:${MCP_PORT}/agent/health" >/dev/null; then
  grn "MCP health OK on Mac"
else
  red "MCP not running on Mac — start with: cd ~/mcp-for-splunk && uv run python src/server.py --transport http --host 0.0.0.0 --port ${MCP_PORT}"
fi

ylw "=== 2) SOAR REST handler (template scaffold — no MCP) ==="
HANDLER="$("${PKG}/scripts/print_sidecar_url.sh" 2>/dev/null | tail -1 || true)"
if [[ -z "$HANDLER" ]]; then
  red "Could not resolve handler URL — check SOAR_URL and credentials in scripts/env.e2e.local"
  exit 1
fi
SCAFFOLD_URL="${HANDLER}?action=scaffold&pattern=hello"
HTTP=$(curl -sk -u "${SOAR_USER}:${SOAR_PASSWORD}" -o /tmp/pb_scaffold.json -w "%{http_code}" "$SCAFFOLD_URL")
if [[ "$HTTP" == "200" ]] && grep -q '"status".*"success"' /tmp/pb_scaffold.json 2>/dev/null; then
  grn "Scaffold HTTP 200 — Playbook Builder app handler works"
else
  red "Scaffold HTTP ${HTTP} — app install or handler broken"
  head -c 400 /tmp/pb_scaffold.json 2>/dev/null || true
  echo
fi

ylw "=== 3) SOAR → MCP tunnel (from SOAR host) ==="
SSH_KEY="${SSH_KEY:-${HOME}/Downloads/tylerkeypair.pem}"
SOAR_HOST="${SOAR_HOST:-10.236.39.108}"
if [[ -f "$SSH_KEY" ]]; then
  if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "splunker@${SOAR_HOST}" \
    "curl -sf -m 5 http://127.0.0.1:${MCP_PORT}/agent/health && echo TUNNEL_OK" 2>/dev/null; then
    grn "SOAR can reach MCP via reverse tunnel"
  else
    red "SOAR cannot reach MCP on 127.0.0.1:${MCP_PORT}"
    ylw "Start tunnel on Mac:"
    ylw "  ssh -i ${SSH_KEY} -N -R ${MCP_PORT}:127.0.0.1:${MCP_PORT} splunker@${SOAR_HOST}"
  fi
else
  ylw "Skip tunnel check — SSH key not found at ${SSH_KEY}"
fi

ylw "=== 4) NL build via SOAR handler (proxies to MCP — may take 20–90s) ==="
CHAT_URL="${HANDLER}"
HTTP=$(curl -sk -u "${SOAR_USER}:${SOAR_PASSWORD}" -m 120 -o /tmp/pb_chat.json -w "%{http_code}" \
  -X POST "$CHAT_URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"chat","message":"Build hello world playbook"}')
if [[ "$HTTP" == "200" ]]; then
  if grep -q '"source"' /tmp/pb_chat.json 2>/dev/null; then
    grn "Chat HTTP 200 with playbook source"
  else
    ylw "Chat HTTP 200 but no source — check error in response:"
    head -c 500 /tmp/pb_chat.json
    echo
  fi
elif [[ "$HTTP" == "500" ]]; then
  red "Chat HTTP 500 — SOAR worker timeout or uncaught exception"
  ylw "Common causes:"
  ylw "  • SOAR handler timeout (~30s) while waiting for Ollama — use Pattern Library or reinstall app v2.9.1+"
  ylw "  • MCP tunnel down during long build"
  head -c 500 /tmp/pb_chat.json 2>/dev/null || true
  echo
else
  red "Chat HTTP ${HTTP}"
  head -c 400 /tmp/pb_chat.json 2>/dev/null || true
  echo
fi

ylw "=== Done ==="
ylw "Sidecar URL: ${HANDLER}"
