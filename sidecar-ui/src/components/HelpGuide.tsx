import type { TroubleshootingEntry } from "../types";
import {
  HelpDemoDataGuide,
  HelpNlRecoveryGuide,
} from "./HelpNlRecoveryGuide";
import { HelpInstallMigrationGuide } from "./HelpInstallMigrationGuide";
import { HelpCustomizeTemplatesGuide } from "./HelpCustomizeTemplatesGuide";
import { HelpPersonasGuide } from "./HelpPersonasGuide";

const WORKFLOW_STEPS = [
  {
    id: "setup",
    title: "Open the builder & check environment",
    body: [
      "In SOAR: Apps → SOAR Playbook Builder → your asset → open the sidecar URL (or launch from a case).",
      "Click the MCP bridge status pill in the header to review environment checks (bridge reachability, asset_defaults, demo cases).",
      "Use Fix environment when offered to apply suggested asset_defaults from the asset config.",
    ],
  },
  {
    id: "template",
    title: "Start from a template (works offline)",
    body: [
      "On the Build tab, open Templates at the bottom. Pick a pattern from the dropdown (Getting started, Identity, ES, etc.).",
      "The header shows how many built-in and org templates are loaded — the library is meant to grow via custom_templates_json on the asset.",
      "Read the detail panel — badges, lab walkthrough, and example NL prompt. Collapse Templates if you need more chat space.",
      "Click Load template. The Chat log and Preview pane update with blocks and Python source.",
    ],
  },
  {
    id: "preview",
    title: "Review preview & code",
    body: [
      "On the right, Preview → Blocks shows each Collect, Action, and Decision in plain language. Hover or click ? for block-type help.",
      "Preview → Code shows syntax-highlighted Python — this is what imports into SOAR.",
      "Optional: Validate scores the draft; Readiness runs a deeper pre-import checklist (code, integrations, placeholders).",
    ],
  },
  {
    id: "nl",
    title: "Describe it in Natural Language (optional)",
    body: [
      "Use the Natural Language box at the bottom of Build when MCP bridge is online.",
      "Offline: keyword templates still match common phrases (e.g. “okta failed login”, “clearpass quarantine”).",
      "Refine in chat; each response updates Preview on the right.",
    ],
  },
  {
    id: "import",
    title: "Import into SOAR",
    body: [
      "Click Readiness to confirm the draft is import-ready (requires app v2.18+). Fix issues or Apply auto-fixes when offered.",
      "Click Import to SOAR. If integrations are missing, map assets in the Integration check panel, then confirm.",
      "Open in SOAR jumps to the playbook in the Visual Playbook Editor after a successful import.",
    ],
  },
  {
    id: "run",
    title: "Run on a case",
    body: [
      "Order matters: Build → Load template → (optional Readiness) → Import to SOAR → Run tab → link case → Run on this case.",
      "Linking a case alone does not enable Readiness or Run — you need a draft (Load template) and an imported playbook.",
      "Run tab → Cases: built-in samples (9001–9005) use Create on SOAR — not Link.",
      "Recommended starters: 9005 (hello), 9002 (phishing), 9004 (ES notable).",
      "If the sidecar URL includes playbook_id= (opened from SOAR), Run can use that id after a case is linked.",
      "Destructive samples (9001, 9003) and templates are lab-only.",
    ],
  },
];

const MODES = [
  {
    label: "Templates only (Mode A)",
    detail:
      "Leave mcp_bridge_url empty. Templates, preview, validate, and import all run on SOAR — no external AI.",
  },
  {
    label: "NL + LLM (Mode B)",
    detail:
      "Set mcp_bridge_url on the asset to your MCP agent bridge. SOAR must reach that URL from the server.",
  },
];

const TABS = [
  { id: "build", label: "Build", detail: "Chat, templates, NL authoring, preview, import" },
  { id: "run", label: "Run", detail: "Case picker, readiness results, run on container" },
  { id: "help", label: "Help", detail: "This guide plus searchable troubleshooting" },
];

interface HelpGuideProps {
  query: string;
  onQueryChange: (q: string) => void;
  entries: TroubleshootingEntry[];
  loading?: boolean;
}

export function HelpGuide({ query, onQueryChange, entries, loading }: HelpGuideProps) {
  return (
    <nav className="help-guide" aria-label="Help topics">
      <details className="help-guide-chapter app-section" open>
        <summary className="help-guide-chapter-summary">First-Time Setup & Migration</summary>
        <div className="help-guide-chapter-body">
          <HelpInstallMigrationGuide />
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">How to Use the Playbook Builder</summary>
        <div className="help-guide-chapter-body">
          <p className="help-guide-intro">
            Pick or describe a playbook → preview → import → run on a case. Templates work without
            AI; natural language needs the MCP bridge when configured.
          </p>
          <div className="help-guide-topics">
            {WORKFLOW_STEPS.map((step, index) => (
              <details key={step.id} className="help-guide-topic">
                <summary>
                  <span className="help-guide-topic-num">{index + 1}.</span>
                  <span className="help-guide-topic-label">{step.title}</span>
                </summary>
                <ul className="help-guide-topic-body">
                  {step.body.map((line) => (
                    <li key={line.slice(0, 48)}>{line}</li>
                  ))}
                </ul>
              </details>
            ))}
            <details className="help-guide-topic">
              <summary>
                <span className="help-guide-topic-label">Operating modes</span>
              </summary>
              <ul className="help-guide-topic-body help-guide-list-plain">
                {MODES.map((mode) => (
                  <li key={mode.label}>
                    <strong>{mode.label}</strong>
                    <span>{mode.detail}</span>
                  </li>
                ))}
              </ul>
            </details>
            <details className="help-guide-topic">
              <summary>
                <span className="help-guide-topic-label">Tabs at a glance</span>
              </summary>
              <dl className="help-guide-tabs">
                {TABS.map((tab) => (
                  <div key={tab.id}>
                    <dt>{tab.label}</dt>
                    <dd>{tab.detail}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </div>
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">Coach, Assistant & Tutor Personas</summary>
        <div className="help-guide-chapter-body">
          <HelpPersonasGuide />
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">Growing & Customizing Templates</summary>
        <div className="help-guide-chapter-body">
          <HelpCustomizeTemplatesGuide />
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">Demo Data & Run Lab Testing</summary>
        <div className="help-guide-chapter-body">
          <HelpDemoDataGuide />
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">Natural Language Testing & Recovery Loop</summary>
        <div className="help-guide-chapter-body">
          <HelpNlRecoveryGuide />
        </div>
      </details>

      <details className="help-guide-chapter app-section">
        <summary className="help-guide-chapter-summary">Troubleshooting</summary>
        <div className="help-guide-chapter-body">
          <p className="help-guide-intro">
            Search symptoms for templates, import, integrations, and running on a case. Works
            offline on SOAR.
          </p>
          <input
            type="search"
            className="help-search"
            placeholder="e.g. invalid datapath, okta, import failed…"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
          />
          {loading && <p className="help-status">Searching…</p>}
          {!loading && entries.length === 0 && query && (
            <p className="help-status">No matches — try okta, import, templates, or datapath.</p>
          )}
          <div className="help-guide-topics">
            {entries.map((entry) => (
              <details key={entry.id} className="help-guide-topic">
                <summary>
                  <span className="help-guide-topic-label">{entry.title}</span>
                </summary>
                <div className="help-guide-topic-body help-guide-troubleshoot">
                  <p className="help-guide-kicker">Symptom</p>
                  <p className="help-guide-symptom">{entry.symptom}</p>
                  <p className="help-guide-kicker">Fix</p>
                  <ol className="help-guide-fix-steps">
                    {entry.fix_steps.map((step) => (
                      <li key={step.slice(0, 48)}>{step}</li>
                    ))}
                  </ol>
                </div>
              </details>
            ))}
          </div>
        </div>
      </details>
    </nav>
  );
}
