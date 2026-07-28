/** In-app guide — how to use the Playbook Builder sidecar (offline, no search required). */

const WORKFLOW_STEPS = [
  {
    id: "setup",
    title: "1. Open the builder & check environment",
    body: [
      "In SOAR: Apps → SOAR Playbook Builder → your asset → open the sidecar URL (or launch from a case).",
      "Click the MCP bridge status pill in the header to review environment checks (bridge reachability, asset_defaults, demo cases).",
      "Use Fix environment when offered to apply suggested asset_defaults from the asset config.",
    ],
  },
  {
    id: "template",
    title: "2. Start from a template (works offline)",
    body: [
      "On the Build tab, open Templates at the bottom. Pick a pattern from the dropdown (Getting started, Identity, ES, etc.).",
      "Read the detail panel — badges, lab walkthrough, and example NL prompt. Collapse Templates if you need more chat space.",
      "Click Load template. The Chat log and Preview pane update with blocks and Python source.",
    ],
  },
  {
    id: "preview",
    title: "3. Review preview & code",
    body: [
      "On the right, Preview → Blocks shows each Collect, Action, and Decision in plain language. Hover ? for block-type help.",
      "Preview → Code shows syntax-highlighted Python — this is what imports into SOAR.",
      "Optional: Validate scores the draft; Readiness runs a deeper pre-import checklist (code, integrations, placeholders).",
    ],
  },
  {
    id: "nl",
    title: "4. Or describe it in natural language (optional)",
    body: [
      "Use the Natural language box at the bottom of Build when MCP bridge is online.",
      "Offline: keyword templates still match common phrases (e.g. “okta failed login”, “clearpass quarantine”).",
      "Refine in chat; each response updates Preview on the right.",
    ],
  },
  {
    id: "import",
    title: "5. Import into SOAR",
    body: [
      "Click Readiness to confirm the draft is import-ready (requires app v2.18+). Fix issues or Apply auto-fixes when offered.",
      "Click Import to SOAR. If integrations are missing, map assets in the Integration check panel, then confirm.",
      "Open in SOAR jumps to the playbook in the Visual Playbook Editor after a successful import.",
    ],
  },
  {
    id: "run",
    title: "6. Run on a case",
    body: [
      "Open the sidecar from a container or use Run tab → link/create a demo case.",
      "After import, use Run on this case (Build or Run tab) to execute against the linked container.",
      "Destructive templates may ask for an extra confirmation in lab only.",
    ],
  },
];

const MODES = [
  {
    label: "Templates only (Mode A)",
    detail: "Leave mcp_bridge_url empty. Templates, preview, validate, and import all run on SOAR — no external AI.",
  },
  {
    label: "NL + LLM (Mode B)",
    detail: "Set mcp_bridge_url on the asset to your MCP agent bridge. SOAR must reach that URL from the server.",
  },
];

export function BuilderWalkthrough() {
  return (
    <section className="help-walkthrough app-section" aria-labelledby="walkthrough-heading">
      <div className="app-section-header">
        <span id="walkthrough-heading">How to use the Playbook Builder</span>
      </div>
      <div className="app-section-body help-walkthrough-body">
        <p className="help-section-desc">
          End-to-end flow: pick or describe a playbook → preview → import → run on a case. Templates
          work without AI; natural language needs the MCP bridge when configured.
        </p>

        <ol className="help-walkthrough-steps">
          {WORKFLOW_STEPS.map((step) => (
            <li key={step.id} className="help-walkthrough-step">
              <strong>{step.title}</strong>
              <ul>
                {step.body.map((line) => (
                  <li key={line.slice(0, 40)}>{line}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>

        <details className="help-walkthrough-fold">
          <summary>Operating modes</summary>
          <ul className="help-walkthrough-modes">
            {MODES.map((m) => (
              <li key={m.label}>
                <strong>{m.label}</strong>
                <span>{m.detail}</span>
              </li>
            ))}
          </ul>
        </details>

        <details className="help-walkthrough-fold">
          <summary>Tabs at a glance</summary>
          <dl className="help-walkthrough-tabs">
            <div>
              <dt>Build</dt>
              <dd>Chat, templates, NL authoring, preview, import</dd>
            </div>
            <div>
              <dt>Run</dt>
              <dd>Case picker, readiness results, run on container</dd>
            </div>
            <div>
              <dt>Help</dt>
              <dd>This guide plus searchable troubleshooting</dd>
            </div>
          </dl>
        </details>
      </div>
    </section>
  );
}
