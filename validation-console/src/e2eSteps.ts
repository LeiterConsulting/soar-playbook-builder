import type { ValidationPhase } from "./types";

export const VALIDATION_PHASES: ValidationPhase[] = [
  {
    id: "1-prerequisites",
    title: "Environment",
    subtitle: "Credentials & targets",
    whatYouDo:
      "Create scripts/env.e2e.local from env.e2e.example with SOAR_URL, SOAR_USER, SOAR_PASSWORD, PB_ASSET, and optional MCP_BRIDGE_URL.",
    whatAutomationDoes:
      "Confirms required environment variables are present before any SOAR HTTP calls.",
    passCriteria: "All required env vars set — no missing SOAR_URL / USER / PASSWORD.",
    linkKeys: [],
  },
  {
    id: "2-soar-platform",
    title: "SOAR platform",
    subtitle: "App installed & asset ready",
    whatYouDo:
      "Install soar_playbook_builder.tgz, enable the app, and create an asset (e.g. mcpbridge). Set ai_instructions if desired.",
    whatAutomationDoes:
      "GET /rest/version, finds Playbook Builder in /rest/app, checks version ≥ 2.7.2, locates your asset.",
    passCriteria: "App enabled, directory registered, asset exists with expected name.",
    linkKeys: ["soar_home", "soar_apps", "soar_app_rest"],
  },
  {
    id: "3-sidecar-api",
    title: "Sidecar API (Mode A core)",
    subtitle: "Scaffold · validate · preview",
    whatYouDo:
      "Optional: open the sidecar in your browser and click Generate template → Validate to mirror what automation runs.",
    whatAutomationDoes:
      "GET sidecar HTML, Hello scaffold, validate score, and builder steps JSON via the REST handler.",
    passCriteria: "Hello scaffold returns Python source; validate returns analysis/score.",
    linkKeys: ["sidecar", "sidecar_hello_scaffold", "sidecar_validate"],
  },
  {
    id: "4-import",
    title: "Import pipeline",
    subtitle: "Package → SOAR playbook repo",
    whatYouDo:
      "After automation imports PB_E2E_Hello_*, open Visual Editor and confirm blocks match Hello World.",
    whatAutomationDoes:
      "POST import_draft with confirm=true, verifies playbook via /rest/playbook/{id}, optionally deletes test playbook.",
    passCriteria: "Import succeeds; playbook visible in REST and VPE link opens.",
    linkKeys: ["sidecar", "soar_playbooks"],
  },
  {
    id: "5-mcp-bridge",
    title: "MCP bridge (Mode B)",
    subtitle: "NL chat & bridge health",
    whatYouDo:
      "Configure mcp_bridge_url on the asset, ensure SOAR server can reach the bridge, run Test connectivity in SOAR.",
    whatAutomationDoes:
      "GET bridge_status from SOAR, GET /agent/health from runner, optional NL message proxy (Mode B).",
    passCriteria: "reachable=true from SOAR when Mode B; sidecar shows AI connected.",
    linkKeys: ["sidecar_bridge_status", "mcp_health", "sidecar"],
  },
  {
    id: "6-manual-signoff",
    title: "Manual sign-off",
    subtitle: "Human eyes before GitHub",
    whatYouDo:
      "Complete each manual row: sidecar UI polish, test connectivity action, VPE opens correct playbook, cleanup PB_E2E_* if kept.",
    whatAutomationDoes:
      "Lists manual checks — you confirm in SOAR UI and mark done in this console.",
    passCriteria: "All ◎ items reviewed; zero unexplained errors in prior phases.",
    linkKeys: ["sidecar", "soar_apps", "soar_playbooks"],
  },
];
