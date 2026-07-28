/** Quick setup actions for fresh installs and migration (Help tab). */

import { useCallback, useEffect, useState } from "react";
import { useBuilder } from "../context/BuilderProvider";

interface EnvPayload {
  setup_complete?: boolean;
  capability_index_loaded?: boolean;
  default_ui_mode?: string;
  checks?: Array<{ id: string; severity: string; title: string; detail: string }>;
}

export function SetupAssistant() {
  const b = useBuilder();
  const [env, setEnv] = useState<EnvPayload | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = (await b.apiGet({ action: "environment_check", _ts: String(Date.now()) })) as EnvPayload;
      setEnv(data);
    } catch {
      setEnv(null);
    }
  }, [b.apiGet]);

  useEffect(() => {
    void refresh();
  }, [refresh, b.envRefreshToken]);

  if (env?.setup_complete) {
    return (
      <section className="setup-assistant setup-assistant-complete app-section" aria-label="Setup status">
        <div className="setup-assistant-head">
          <strong>First-time setup complete</strong>
          <span className="setup-assistant-sub">
            Capability index is loaded and blocking checks passed. Ongoing admin actions moved to
            the header.
          </span>
        </div>
        <p className="setup-assistant-hint">
          Open the <strong>Environment menu</strong> (header pill — e.g. AI connected / Offline
          mode) for <strong>Rebuild capability index</strong>, <strong>Run self-test</strong>, and{" "}
          <strong>Export asset config</strong>. URL <code>mode=</code> and persona docs are under{" "}
          <strong>Coach, Assistant &amp; Tutor Personas</strong> below.
        </p>
      </section>
    );
  }

  const capMissing = env?.capability_index_loaded === false;

  return (
    <section className="setup-assistant app-section" aria-label="Setup assistant">
      <div className="setup-assistant-head">
        <strong>Setup assistant</strong>
        <span className="setup-assistant-sub">
          {capMissing
            ? "Finish first-time setup on this SOAR instance (~5 min)."
            : "Optional checks to confirm your environment."}
        </span>
      </div>
      <ol className="setup-assistant-steps">
        <li className={env?.capability_index_loaded ? "done" : "pending"}>
          Rebuild capability index (harvests local apps and actions)
        </li>
        <li>Run self-test (templates, demo cases, optional bridge)</li>
        <li>Export asset config before migrating SOAR (save JSON backup)</li>
        <li>
          Set <code>default_ui_mode</code> on the asset (optional) —{" "}
          <code>coach</code>, <code>assistant</code>, or <code>tutor</code>; URL{" "}
          <code>mode=</code> overrides
        </li>
        <li>Smoke test: Run tab → sample 9005 → Create on SOAR</li>
      </ol>
      <p className="setup-assistant-hint">
        After rebuild succeeds, this panel becomes a short &quot;setup complete&quot; note — use
        the Environment menu for the same actions anytime.
      </p>
      <div className="setup-assistant-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={b.fixingEnvironment}
          onClick={() => void b.handleSetupAction("rebuild_capability_index")}
        >
          {b.fixingEnvironment ? "Working…" : "Rebuild capability index"}
        </button>
        <button
          type="button"
          className="btn secondary"
          disabled={b.fixingEnvironment}
          onClick={() => void b.handleSetupAction("run_self_test")}
        >
          Run self-test
        </button>
        <button
          type="button"
          className="btn secondary"
          disabled={b.fixingEnvironment}
          onClick={() => void b.handleSetupAction("export_asset_config")}
        >
          Export asset config
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={b.fixingEnvironment}
          onClick={() => void refresh()}
        >
          Refresh status
        </button>
      </div>
      {env?.checks && capMissing && (
        <p className="setup-assistant-hint">
          Capability index:{" "}
          {env.checks.find((c) => c.id === "capability_index")?.detail ?? "not built yet"}
        </p>
      )}
      {env?.default_ui_mode && env.default_ui_mode !== "studio" && (
        <p className="setup-assistant-hint">
          Asset default persona: <code>{env.default_ui_mode}</code> — append{" "}
          <code>?mode=studio</code> to force full studio UI.
        </p>
      )}
    </section>
  );
}
