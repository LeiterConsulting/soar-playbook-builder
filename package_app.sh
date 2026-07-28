#!/usr/bin/env bash
# Package SOAR Playbook Builder app for install via SOAR Apps UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DIST="$ROOT/dist"
APP_DIR="soar_playbook_builder"
APP_NAME="soar_playbook_builder"

rm -rf "$DIST"
mkdir -p "$DIST"

if [[ -f "$ROOT/sidecar-ui/package.json" ]]; then
  echo "Building React sidecar UI..."
  (cd "$ROOT/sidecar-ui" && npm ci && npm run build)
fi

# Prevent macOS AppleDouble (._*) resource forks from polluting the tarball.
export COPYFILE_DISABLE=1
find "$ROOT/$APP_DIR" -name '._*' -delete 2>/dev/null || true
find "$ROOT/$APP_DIR" -name '.DS_Store' -delete 2>/dev/null || true
find "$ROOT/$APP_DIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Ship bundled demo metadata for optional asset sample_cases_json overrides.
if [[ -d "$ROOT/sample_data" ]]; then
  echo "Bundling sample_data/ into app package..."
  rm -rf "$ROOT/$APP_DIR/sample_data"
  cp -R "$ROOT/sample_data" "$ROOT/$APP_DIR/sample_data"
fi

# Ship customer-facing docs inside the app (offline / air-gap handoff).
if [[ -d "$ROOT/docs" ]]; then
  echo "Bundling docs/ into app package..."
  rm -rf "$ROOT/$APP_DIR/docs"
  mkdir -p "$ROOT/$APP_DIR/docs"
  for doc in \
    FRESH_INSTALL_AND_MIGRATION.md \
    WHATS_NEW_PLAIN_ENGLISH.md \
    CUSTOMIZATION.md \
    COACH_PERSONAS.md \
    RUN_TAB_DEMO.md \
    PLAYBOOK_BUILDER_GUIDE.md \
    REPLICATION_HANDOFF.md \
    AIR_GAPPED_OPERATIONS.md; do
    if [[ -f "$ROOT/docs/$doc" ]]; then
      cp "$ROOT/docs/$doc" "$ROOT/$APP_DIR/docs/$doc"
    fi
  done
fi

# SOAR requires a single top-level directory in the tarball (no extra files at root).
tar -czf "$DIST/${APP_NAME}.tgz" \
  --exclude='._*' \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  -C "$ROOT" "$APP_DIR"

echo "Built $DIST/${APP_NAME}.tgz"
echo ""
if [[ -f "$ROOT/utility_playbooks/package_utility_playbooks.py" ]]; then
  echo "Packaging utility playbooks..."
  python3 "$ROOT/utility_playbooks/package_utility_playbooks.py"
fi
echo ""
if tar -tzf "$DIST/${APP_NAME}.tgz" | rg -q '\._'; then
  echo "WARNING: tarball still contains AppleDouble files" >&2
else
  echo "Verified: no AppleDouble (._*) files in tarball"
fi
echo ""
echo "Install: SOAR → Apps → Install App → select dist/${APP_NAME}.tgz"
echo ""
echo "After install:"
echo "  1. Create an asset and set ai_instructions (optional header text)"
echo "  2. Templates-only: leave mcp_bridge_url empty — scaffolds, import, and demo cases work on SOAR"
echo "  3. NL + LLM: set mcp_bridge_url to your MCP bridge (see docs/ARCHITECTURE.md)"
echo "  4. Run tab: use built-in sample cases 9001–9005 → Create on SOAR to test end-to-end"
echo "  5. Test connectivity action, then open /rest/handler/<directory>/<asset>/chat"
echo "     (directory from REST app.directory, e.g. soarplaybookbuilder_<uuid>)"
echo ""
echo "Documentation: docs/PLAYBOOK_BUILDER_GUIDE.md · docs/RUN_TAB_DEMO.md · docs/NL_TESTING_AND_RECOVERY.md"
