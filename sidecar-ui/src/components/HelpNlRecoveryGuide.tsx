/** In-app natural language testing & recovery guide (mirrors docs/NL_TESTING_AND_RECOVERY.md). */

const RECOVERY_TIERS = [
  {
    tier: "Tier 1 — Rephrase",
    time: "~30 sec",
    steps: [
      'Start with “Build a playbook that…”',
      "Name one integration you have onboarded (Okta, ServiceNow, …).",
      "Avoid explain / how do I for scaffold generation.",
    ],
  },
  {
    tier: "Tier 2 — Nearest template",
    time: "~5 min",
    steps: [
      "Templates → pick closest pattern (es-notable-response, servicenow-incident, …).",
      "Load template → confirm Preview → narrow follow-up in chat (Mode B) or edit in VPE.",
    ],
  },
  {
    tier: "Tier 3 — Environment",
    time: "~5–10 min",
    steps: [
      "Fix mcp_bridge_url or use Templates only (Mode A).",
      "Environment menu → Fix environment for asset_defaults.",
      "Run tab → Create on SOAR for a demo sample when no live case exists.",
    ],
  },
  {
    tier: "Tier 4 — Product gap",
    time: "Document",
    steps: [
      "Capture prompt, mode, Readiness output, and case ID.",
      "Short-term: strict org IR template via custom_ir_templates_json.",
      "Long-term: add scaffold + keywords in a future release.",
    ],
  },
];

const DEMO_SAMPLES = [
  { id: 9005, pattern: "hello", tier: "safe", note: "Smallest end-to-end Run tab check" },
  { id: 9002, pattern: "phishing-enrichment", tier: "safe", note: "Recommended showcase" },
  { id: 9004, pattern: "es-notable-response", tier: "safe", note: "Note-only ES response" },
  { id: 9001, pattern: "failed-logins-okta", tier: "destructive", note: "Lab only — Okta disable" },
  { id: 9003, pattern: "insider-threat-ad", tier: "destructive", note: "Lab only — AD actions" },
];

export function HelpDemoDataGuide() {
  return (
    <div className="help-guide-nl-body">
      <p className="help-guide-intro">
        Five built-in <strong>sample cases</strong> (9001–9005) and matching{" "}
        <strong>runtime fixtures</strong> ship with every install. No ES export or live notable
        required to vet Build → Import → Run.
      </p>
      <ol className="help-guide-topic-body">
        <li>
          <strong>Build</strong> — load a template (start with <code>hello</code>,{" "}
          <code>phishing-enrichment</code>, or <code>es-notable-response</code>) and Import to SOAR.
        </li>
        <li>
          <strong>Run</strong> — expand Cases → pick a row marked <span className="case-badge showcase">demo pick</span>{" "}
          → <strong>Create on SOAR</strong> (not Link — samples are metadata until provisioned).
        </li>
        <li>
          <strong>Readiness</strong> → <strong>Run on this case</strong> against the new container.
        </li>
      </ol>
      <table className="help-demo-table">
        <thead>
          <tr>
            <th>Sample ID</th>
            <th>Fixture</th>
            <th>Tier</th>
            <th>Use for</th>
          </tr>
        </thead>
        <tbody>
          {DEMO_SAMPLES.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>
                <code>{row.pattern}</code>
              </td>
              <td>
                <span className={`case-badge tier-${row.tier}`}>
                  {row.tier === "safe" ? "safe demo" : "lab only"}
                </span>
              </td>
              <td>{row.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="help-guide-footnote">
        Optional: paste <code>sample_data/sample_cases.json</code> from the app bundle into the asset{" "}
        <code>sample_cases_json</code> field to merge org-specific demos. Built-in samples work
        without any asset configuration.
      </p>
    </div>
  );
}

export function HelpRecoveryFlowchart() {
  return (
    <div
      className="help-recovery-flow"
      role="figure"
      aria-label="Natural Language testing and recovery loop"
    >
      <figcaption className="help-recovery-flow-caption">
        Iterative recovery loop — use whenever NL fails, data is missing, or import/run breaks.
      </figcaption>
      <div className="help-recovery-flow-track">
        <div className="help-flow-node">User NL request</div>
        <div className="help-flow-arrow" aria-hidden="true" />
        <div className="help-flow-decision">Build intent?</div>
        <div className="help-flow-branches">
          <div className="help-flow-branch">
            <span className="help-flow-branch-label">No</span>
            <div className="help-flow-node help-flow-node-muted">
              Rephrase: “Build a playbook that…”
            </div>
          </div>
          <div className="help-flow-branch">
            <span className="help-flow-branch-label">Yes</span>
            <div className="help-flow-decision">Bridge up?</div>
          </div>
        </div>
        <div className="help-flow-split">
          <div className="help-flow-col">
            <p className="help-flow-col-title">Offline (Mode A)</p>
            <div className="help-flow-decision">Keyword match?</div>
            <div className="help-flow-node">Template loaded → Preview</div>
            <div className="help-flow-node help-flow-node-warn">
              No match → generic stub (not production-ready)
            </div>
          </div>
          <div className="help-flow-col">
            <p className="help-flow-col-title">Bridge (Mode B)</p>
            <div className="help-flow-node">LLM draft → Preview / Code</div>
          </div>
        </div>
        <div className="help-flow-arrow" aria-hidden="true" />
        <div className="help-flow-node help-flow-node-accent">Readiness</div>
        <div className="help-flow-decision">ready_for_import?</div>
        <div className="help-flow-branches">
          <div className="help-flow-branch">
            <span className="help-flow-branch-label">No</span>
            <div className="help-flow-node">Fix assets / code / nearest template</div>
          </div>
          <div className="help-flow-branch">
            <span className="help-flow-branch-label">Yes</span>
            <div className="help-flow-node">Import to SOAR</div>
          </div>
        </div>
        <div className="help-flow-decision">needs_assets?</div>
        <div className="help-flow-node">Map integrations → link case → Readiness again</div>
        <div className="help-flow-decision">ready_for_run?</div>
        <div className="help-flow-node help-flow-node-success">Run on case</div>
      </div>
      <p className="help-guide-footnote">
        Full walkthrough, test prompts, and gap-handling tables:{" "}
        <code>docs/NL_TESTING_AND_RECOVERY.md</code> in the app repository (Mermaid flowchart on
        GitHub).
      </p>
    </div>
  );
}

export function HelpNlRecoveryGuide() {
  return (
    <div className="help-guide-nl-body">
      <p className="help-guide-intro">
        Use this loop for QA, pilots, and operator training when chat returns a stub, import blocks,
        or Run on case fails.
      </p>
      <p className="help-guide-footnote">
        <strong>Templates vs Natural Language:</strong> Short prompts that name one shipped integration
        (e.g. “failed logins with Okta”) may load a catalog template when the MCP bridge is offline.
        Multi-integration or approval-gate asks (PagerDuty, Teams, analyst hold) skip keyword templates
        and use the LLM when the bridge is up, or a generic starter stub offline — not a wrong
        template.
      </p>
      <HelpRecoveryFlowchart />
      <p className="help-guide-kicker">Recovery tiers</p>
      <div className="help-guide-topics">
        {RECOVERY_TIERS.map((block) => (
          <details key={block.tier} className="help-guide-topic">
            <summary>
              <span className="help-guide-topic-label">{block.tier}</span>
              <span className="help-guide-topic-meta">{block.time}</span>
            </summary>
            <ul className="help-guide-topic-body">
              {block.steps.map((step) => (
                <li key={step.slice(0, 48)}>{step}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>
      <p className="help-guide-kicker">Stress-test prompt (outside catalog)</p>
      <blockquote className="help-guide-quote">
        Build a playbook that creates a PagerDuty incident when a critical ES notable fires, posts a
        summary to Microsoft Teams, and holds execution until an analyst approves in the case before
        running any containment actions.
      </blockquote>
      <p className="help-guide-footnote">
        Offline: expect generic stub + warnings. After testing, confirm routing with a known
        integration prompt (e.g. ServiceNow P1 + case note).
      </p>
    </div>
  );
}
