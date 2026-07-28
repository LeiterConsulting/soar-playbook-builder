/** In-app first-time setup & migration checklist (mirrors docs/FRESH_INSTALL_AND_MIGRATION.md). */

const MODE_A_STEPS = [
  "Install soar_playbook_builder.tgz — Apps → Install App.",
  "Create a Playbook Builder asset (e.g. playbook_builder). Leave mcp_bridge_url empty for templates-only Mode A.",
  "Run asset actions: get sidecar url → rebuild capability index → capability index status.",
  "Open the sidecar URL; click the header status pill → confirm Capability index and Demo cases rows.",
  "Run tab → sample 9005 (hello) → Create on SOAR → Build → Hello template → Import → Run on case.",
];

const MODE_B_EXTRA = [
  "Deploy MCP agent bridge on a host SOAR can reach; configure LLM on the bridge host.",
  "Set mcp_bridge_url on the asset (e.g. https://bridge.internal:8003/agent). Plain HTTP requires the lab-only override.",
  "Run test connectivity on the asset — sidecar pill should show AI connected when LLM is configured.",
];

const MIGRATION_BEFORE_SHUTDOWN = [
  "Export Playbook Builder asset configuration (asset_defaults, mcp_bridge_url, es_web_url, custom_ir_templates_json, etc.).",
  "Export any playbooks you authored on the old SOAR (Playbooks → export).",
  "Save dist/soar_playbook_builder.tgz and MCP bridge host/LLM settings.",
];

const MIGRATION_ON_NEW_SOAR = [
  "Install .tgz → create asset → paste saved asset configuration.",
  "Run rebuild capability index (index is per-instance — not migrated).",
  "Re-import exported playbooks; re-run ES stitch if using Mission Control links.",
];

export function HelpInstallMigrationGuide() {
  return (
    <div className="help-install-guide">
      <p className="help-guide-intro">
        Moving to a new SOAR instance is a <strong>fresh install + asset reconfiguration</strong> — not
        a database migration. Templates, demo cases (9001–9005), and Help content ship in the app.
        Typical Mode A setup: <strong>15–20 minutes</strong>.
      </p>

      <details className="help-guide-topic" open>
        <summary>
          <span className="help-guide-topic-label">Mode A — templates only (~15 min)</span>
        </summary>
        <ol className="help-guide-topic-body help-guide-numbered">
          {MODE_A_STEPS.map((line) => (
            <li key={line.slice(0, 40)}>{line}</li>
          ))}
        </ol>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">Mode B — add MCP + LLM</span>
        </summary>
        <ol className="help-guide-topic-body help-guide-numbered">
          {MODE_B_EXTRA.map((line) => (
            <li key={line.slice(0, 40)}>{line}</li>
          ))}
        </ol>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">Before your old SOAR shuts down</span>
        </summary>
        <ul className="help-guide-topic-body">
          {MIGRATION_BEFORE_SHUTDOWN.map((line) => (
            <li key={line.slice(0, 40)}>{line}</li>
          ))}
        </ul>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">On the new SOAR instance</span>
        </summary>
        <ul className="help-guide-topic-body">
          {MIGRATION_ON_NEW_SOAR.map((line) => (
            <li key={line.slice(0, 40)}>{line}</li>
          ))}
        </ul>
      </details>

      <p className="help-guide-footnote">
        <strong>Setup assistant:</strong> On Help, rebuild capability index once on a new SOAR instance.
        When setup completes, that panel shows a short &quot;setup complete&quot; note and ongoing actions
        move to the header <strong>Environment menu</strong> (pill next to AI connected / Offline mode) —
        rebuild index, self-test, export asset config. Full guide ships in{" "}
        <code>soar_playbook_builder/docs/FRESH_INSTALL_AND_MIGRATION.md</code> on SOAR.
      </p>
    </div>
  );
}
