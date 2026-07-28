#!/usr/bin/env bash
# Package SOAR Playbook Builder app for install via SOAR Apps UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DIST="$ROOT/dist"
APP_DIR="soar_playbook_builder"
APP_NAME="soar_playbook_builder"
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/soar-playbook-builder-package.XXXXXX")"

cleanup() {
  if [[ -n "$STAGING" && -d "$STAGING" ]]; then
    rm -rf -- "$STAGING"
  fi
}
trap cleanup EXIT

rm -rf "$DIST"
mkdir -p "$DIST"

if [[ -f "$ROOT/sidecar-ui/package.json" ]]; then
  echo "Building React sidecar UI..."
  (cd "$ROOT/sidecar-ui" && npm ci && npm run build)
fi

# Prevent macOS AppleDouble (._*) resource forks from polluting the tarball.
export COPYFILE_DISABLE=1
cp -R "$ROOT/$APP_DIR" "$STAGING/$APP_DIR"
find "$STAGING/$APP_DIR" -name '._*' -delete 2>/dev/null || true
find "$STAGING/$APP_DIR" -name '.DS_Store' -delete 2>/dev/null || true
find "$STAGING/$APP_DIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT/LICENSE" "$STAGING/$APP_DIR/LICENSE"
cp "$ROOT/ATTRIBUTION.md" "$STAGING/$APP_DIR/ATTRIBUTION.md"
mkdir -p "$STAGING/$APP_DIR/THIRD_PARTY_LICENSES"
cp "$ROOT/sidecar-ui/node_modules/react/LICENSE" \
  "$STAGING/$APP_DIR/THIRD_PARTY_LICENSES/react-MIT.txt"
cp "$ROOT/sidecar-ui/node_modules/react-dom/LICENSE" \
  "$STAGING/$APP_DIR/THIRD_PARTY_LICENSES/react-dom-MIT.txt"
cp "$ROOT/sidecar-ui/node_modules/highlight.js/LICENSE" \
  "$STAGING/$APP_DIR/THIRD_PARTY_LICENSES/highlight.js-BSD-3-Clause.txt"

# Ship bundled demo metadata for optional asset sample_cases_json overrides.
if [[ -d "$ROOT/sample_data" ]]; then
  echo "Bundling sample_data/ into app package..."
  rm -rf "$STAGING/$APP_DIR/sample_data"
  cp -R "$ROOT/sample_data" "$STAGING/$APP_DIR/sample_data"
fi

# Ship customer-facing docs inside the app (offline / air-gap handoff).
if [[ -d "$ROOT/docs" ]]; then
  echo "Bundling docs/ into app package..."
  rm -rf "$STAGING/$APP_DIR/docs"
  mkdir -p "$STAGING/$APP_DIR/docs"
  for doc in \
    FRESH_INSTALL_AND_MIGRATION.md \
    WHATS_NEW_PLAIN_ENGLISH.md \
    CUSTOMIZATION.md \
    COACH_PERSONAS.md \
    RUN_TAB_DEMO.md \
    PLAYBOOK_BUILDER_GUIDE.md \
    IR_CONTRACT.md \
    COMPILER_CONTRACT.md \
    GAP_REPORT_CONTRACT.md \
    NO_MODEL_EVAL.md \
    MODEL_BOUNDARY.md \
    RETRIEVAL_CONTRACT.md \
    TRUSTED_REVIEW.md \
    THREAT_MODEL.md \
    OFFLINE_FOUNDATION_IMPLEMENTATION.md \
    OFFLINE_READINESS.md \
    ON_PREM_LLM.md \
    ARCHITECTURE.md \
    MCP_INTEGRATION.md \
    NL_TESTING_AND_RECOVERY.md \
    RUNTIME_VALIDATION.md \
    E2E_VALIDATION.md \
    REPLICATION_HANDOFF.md \
    AIR_GAPPED_OPERATIONS.md; do
    if [[ -f "$ROOT/docs/$doc" ]]; then
      cp "$ROOT/docs/$doc" "$STAGING/$APP_DIR/docs/$doc"
    fi
  done
fi

# SOAR requires one top-level directory. Metadata and gzip timestamps are
# normalized so identical source produces an identical archive.
python3 "$ROOT/scripts/build_app_archive.py" \
  --app-dir "$STAGING/$APP_DIR" \
  --output "$DIST/${APP_NAME}.tgz"
python3 "$ROOT/scripts/inspect_app_archive.py" \
  "$DIST/${APP_NAME}.tgz"

echo "Built $DIST/${APP_NAME}.tgz"
echo ""
if [[ -f "$ROOT/utility_playbooks/package_utility_playbooks.py" ]]; then
  echo "Packaging utility playbooks..."
  python3 "$ROOT/utility_playbooks/package_utility_playbooks.py"
fi
echo ""
if tar -tzf "$DIST/${APP_NAME}.tgz" | grep -q '\._'; then
  echo "WARNING: tarball still contains AppleDouble files" >&2
else
  echo "Verified: no AppleDouble (._*) files in tarball"
fi
echo ""
echo "Install: SOAR → Apps → Install App → select dist/${APP_NAME}.tgz"
echo ""
echo "After install:"
echo "  1. Create an asset and set ai_instructions (optional header text)"
echo "  2. Leave mcp_bridge_url empty for the offline template/review path"
echo "  3. NL + LLM: set mcp_bridge_url to your MCP bridge (see docs/ARCHITECTURE.md)"
echo "  4. Trusted IR Import remains locked pending live qualification; legacy Import/Run is lab-only"
echo "  5. Test connectivity action, then open /rest/handler/<directory>/<asset>/chat"
echo "     (directory from REST app.directory, e.g. soarplaybookbuilder_<uuid>)"
echo ""
echo "Documentation: docs/PLAYBOOK_BUILDER_GUIDE.md · docs/RUN_TAB_DEMO.md · docs/NL_TESTING_AND_RECOVERY.md"
