/** Guided wizard scenarios — offline-first, no LLM required. */
export interface WizardStep {
  id: string;
  title: string;
  detail: string;
}

export interface WizardScenario {
  id: string;
  label: string;
  description: string;
  pattern: string;
  integrations: string[];
  steps: WizardStep[];
  examplePrompt: string;
  troubleshootingIds: string[];
}

export const WIZARD_SCENARIOS: WizardScenario[] = [
  {
    id: "failed-logins-okta",
    label: "Excessive Failed Logins → Okta",
    description:
      "Access — Excessive Failed Logins: lookup Okta user, clear sessions and disable on high/critical severity.",
    pattern: "failed-logins-okta",
    integrations: ["okta"],
    troubleshootingIds: ["okta_asset_missing", "okta_get_user_failed", "es_soar_export_missing"],
    examplePrompt:
      "Build a playbook for Access Excessive Failed Logins that looks up the user in Okta, clears sessions and disables the account when severity is high or critical.",
    steps: [
      {
        id: "pick",
        title: "Pick scenario",
        detail: "Excessive Failed Logins uses artifact cef.user or cef.destinationUserName.",
      },
      {
        id: "okta",
        title: "Configure Okta",
        detail: "Apps → Okta → create asset (e.g. okta). Set asset_defaults: {\"okta\": \"okta\"}.",
      },
      {
        id: "generate",
        title: "Generate template",
        detail: "Click Start below or Use template — preview Python on the right.",
      },
      {
        id: "preflight",
        title: "Asset preflight",
        detail: "Resolve any missing integrations in the panel before Import.",
      },
      {
        id: "import",
        title: "Import to SOAR",
        detail: "Import → wait for ✓ Synced → Open in SOAR (Visual Editor).",
      },
      {
        id: "test",
        title: "Test run",
        detail:
          "Manual container: add user artifact with cef.user, set severity high, run playbook from Playbooks tab.",
      },
    ],
  },
  {
    id: "es-notable-response",
    label: "ES Notable Response",
    description: "Triage ES notables with note and assign — works before ES–SOAR export is wired.",
    pattern: "es-notable-response",
    integrations: [],
    troubleshootingIds: ["es_soar_export_missing", "import_failed"],
    examplePrompt: "Build an ES notable response playbook that adds a note and assigns the container.",
    steps: [
      {
        id: "generate",
        title: "Generate template",
        detail: "Use ES Notable Response pattern — no external integrations required for the stub.",
      },
      {
        id: "import",
        title: "Import",
        detail: "Import to SOAR and set playbook label es_notable_response for ES pairing later.",
      },
      {
        id: "es",
        title: "Wire ES (optional)",
        detail: "ES → Incident Review → Splunk SOAR Integration when export is approved.",
      },
    ],
  },
  {
    id: "servicenow-p1",
    label: "ServiceNow P1 Incident",
    description: "Create P1 ticket from container severity and owner.",
    pattern: "servicenow-incident",
    integrations: ["servicenow"],
    troubleshootingIds: ["needs_assets", "import_failed"],
    examplePrompt:
      "Build a ServiceNow playbook that creates a P1 incident from container severity and owner.",
    steps: [
      {
        id: "snow",
        title: "ServiceNow asset",
        detail: "Install ServiceNow app; create asset servicenow; test connectivity.",
      },
      {
        id: "generate",
        title: "Generate & import",
        detail: "Use template → preflight → Import.",
      },
    ],
  },
  {
    id: "clearpass-quarantine",
    label: "ClearPass Quarantine",
    description: "NAC quarantine when posture fails or risk score ≥ 70.",
    pattern: "clearpass-quarantine",
    integrations: ["clearpass_cppm", "splunk_enterprise"],
    troubleshootingIds: ["needs_assets"],
    examplePrompt: "Build a ClearPass quarantine playbook when risk score is 70 or higher.",
    steps: [
      {
        id: "assets",
        title: "ClearPass + Splunk HEC",
        detail: "Configure clearpass_cppm and splunk_enterprise assets on SOAR.",
      },
      {
        id: "generate",
        title: "Generate & import",
        detail: "Use template → preflight → Import.",
      },
    ],
  },
  {
    id: "hello",
    label: "Hello World (smoke test)",
    description: "Minimal playbook to verify sidecar, import, and VPE without integrations.",
    pattern: "hello",
    integrations: [],
    troubleshootingIds: ["sidecar_blank_404", "import_failed"],
    examplePrompt: "Build a minimal hello world playbook.",
    steps: [
      {
        id: "generate",
        title: "Generate",
        detail: "Select Hello World → Use template.",
      },
      {
        id: "import",
        title: "Import",
        detail: "Import → Open in SOAR to confirm lab is working.",
      },
    ],
  },
];

export function getScenario(id: string): WizardScenario | undefined {
  return WIZARD_SCENARIOS.find((s) => s.id === id);
}
