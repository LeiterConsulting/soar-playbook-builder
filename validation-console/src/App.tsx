import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchConfig,
  fetchHealth,
  statusIcon,
  streamE2E,
  worstPhaseStatus,
} from "./api";
import { VALIDATION_PHASES } from "./e2eSteps";
import type { CheckStatus, ConsoleConfig, E2ECheck, E2EReport } from "./types";

type RunMode = "auto" | "A" | "B";

export function App() {
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [config, setConfig] = useState<ConsoleConfig | null>(null);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [mode, setMode] = useState<RunMode>("auto");
  const [skipImport, setSkipImport] = useState(false);
  const [running, setRunning] = useState(false);
  const [liveChecks, setLiveChecks] = useState<E2ECheck[]>([]);
  const [report, setReport] = useState<E2EReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [manualDone, setManualDone] = useState<Record<string, boolean>>({});

  const phase = VALIDATION_PHASES[phaseIndex];

  const refresh = useCallback(async () => {
    const ok = await fetchHealth();
    setApiUp(ok);
    if (ok) setConfig(await fetchConfig());
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const checksForPhase = useMemo(() => {
    const src = report?.checks ?? liveChecks;
    return src.filter((c) => c.phase === phase.id);
  }, [report, liveChecks, phase.id]);

  const links = report?.links ?? {};

  const runPhase = useCallback(
    (phaseId?: string) => {
      setError(null);
      setRunning(true);
      setLiveChecks([]);
      setReport(null);
      const phases = phaseId ? [phaseId] : undefined;

      const cancel = streamE2E(
        { mode, skipImport, phases },
        {
          onCheck: (c) => setLiveChecks((prev) => [...prev, c]),
          onDone: (r) => {
            setReport(r);
            setRunning(false);
          },
          onError: (msg) => {
            setError(msg);
            setRunning(false);
          },
        },
      );
      return cancel;
    },
    [mode, skipImport],
  );

  const runAll = useCallback(() => {
    setError(null);
    setRunning(true);
    setLiveChecks([]);
    setReport(null);
    streamE2E(
      { mode, skipImport },
      {
        onCheck: (c) => setLiveChecks((prev) => [...prev, c]),
        onDone: (r) => {
          setReport(r);
          setRunning(false);
        },
        onError: (msg) => {
          setError(msg);
          setRunning(false);
        },
      },
    );
  }, [mode, skipImport]);

  const phaseStatus = (id: string): CheckStatus | "pending" => {
    const src = report?.checks ?? liveChecks;
    if (!src.length) return "pending";
    const w = worstPhaseStatus(src, id);
    return (w as CheckStatus) ?? "pending";
  };

  return (
    <div className="console">
      <header className="topbar">
        <div>
          <h1>Playbook Builder</h1>
          <span className="subtitle">E2E validation console</span>
        </div>
        <div className="topbar-meta">
          <span className={`api-pill ${apiUp ? "up" : "down"}`}>
            API {apiUp ? "connected" : "offline"}
          </span>
          {report && (
            <span className={`overall status-${report.status}`}>
              Overall: {report.status}
            </span>
          )}
        </div>
      </header>

      {apiUp === false && (
        <div className="banner error">
          Start the API: <code>./scripts/run-e2e-console.sh</code> or{" "}
          <code>uv run python scripts/e2e_server.py</code>
        </div>
      )}

      {config && !config.envReady && (
        <div className="banner warn">
          Missing env: {config.missingEnv.join(", ")} — copy{" "}
          <code>scripts/env.e2e.example</code> → <code>scripts/env.e2e.local</code>
        </div>
      )}

      <div className="layout">
        <aside className="sidebar">
          <section className="panel">
            <h2>Run</h2>
            <label className="field">
              Mode
              <select
                value={mode}
                disabled={running}
                onChange={(e) => setMode(e.target.value as RunMode)}
              >
                <option value="auto">Auto (bridge optional)</option>
                <option value="A">A — Localized only</option>
                <option value="B">B — Require MCP</option>
              </select>
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={skipImport}
                disabled={running}
                onChange={(e) => setSkipImport(e.target.checked)}
              />
              Skip import step
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={running || !apiUp}
              onClick={runAll}
            >
              {running ? "Running…" : "Validate entire app"}
            </button>
            <button
              type="button"
              className="btn"
              disabled={running || !apiUp}
              onClick={() => runPhase(phase.id)}
            >
              Run this phase only
            </button>
          </section>

          {config && (
            <section className="panel config-panel">
              <h2>Target</h2>
              <dl>
                <dt>SOAR</dt>
                <dd>
                  <a href={config.soarUrl || "#"} target="_blank" rel="noreferrer">
                    {config.soarUrl || "—"}
                  </a>
                </dd>
                <dt>User</dt>
                <dd>{config.soarUser || "—"}</dd>
                <dt>Asset</dt>
                <dd>{config.assetName}</dd>
                <dt>MCP bridge</dt>
                <dd className="mono">{config.mcpBridgeUrl}</dd>
              </dl>
            </section>
          )}

          <nav className="phase-nav">
            {VALIDATION_PHASES.map((p, i) => {
              const st = phaseStatus(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  className={`phase-nav-item${i === phaseIndex ? " active" : ""} status-${st}`}
                  onClick={() => setPhaseIndex(i)}
                >
                  <span className="phase-icon">{st === "pending" ? "○" : statusIcon(st)}</span>
                  <span>
                    <strong>{p.title}</strong>
                    <small>{p.subtitle}</small>
                  </span>
                </button>
              );
            })}
          </nav>

          {report && (
            <section className="panel">
              <h2>Reports</h2>
              <a className="link-btn" href="/api/e2e/report.html" target="_blank" rel="noreferrer">
                Open HTML report
              </a>
            </section>
          )}
        </aside>

        <main className="main">
          <article className="phase-card">
            <div className="phase-head">
              <span className="phase-num">Phase {phaseIndex + 1} / {VALIDATION_PHASES.length}</span>
              <h2>{phase.title}</h2>
              <p className="phase-sub">{phase.subtitle}</p>
            </div>

            <div className="guide-grid">
              <section>
                <h3>What you do</h3>
                <p>{phase.whatYouDo}</p>
              </section>
              <section>
                <h3>What the button runs</h3>
                <p>{phase.whatAutomationDoes}</p>
              </section>
              <section>
                <h3>Pass criteria</h3>
                <p>{phase.passCriteria}</p>
              </section>
            </div>

            {phase.linkKeys.length > 0 && (
              <section className="quick-links">
                <h3>Quick verify links</h3>
                <div className="link-row">
                  {phase.linkKeys.map((key) => {
                    const url = links[key];
                    if (!url && !report) {
                      return (
                        <span key={key} className="link-chip muted">
                          {key} (run validation first)
                        </span>
                      );
                    }
                    if (!url) return null;
                    return (
                      <a
                        key={key}
                        className="link-chip"
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        title={url}
                      >
                        {key.replace(/_/g, " ")} ↗
                      </a>
                    );
                  })}
                </div>
              </section>
            )}

            {error && <div className="inline-error">{error}</div>}

            <section className="live-panel">
              <div className="live-head">
                <h3>Live results {running && <span className="pulse">● running</span>}</h3>
              </div>
              {checksForPhase.length === 0 && !running && (
                <p className="hint">Click Run to execute automated checks for this phase.</p>
              )}
              <ul className="check-list">
                {checksForPhase.map((c) => (
                  <li key={c.id} className={`check-row status-${c.status}`}>
                    <span className="check-icon">{statusIcon(c.status)}</span>
                    <div className="check-body">
                      <strong>{c.title}</strong>
                      <span className="check-msg">{c.message}</span>
                      {c.manual_verify && (
                        <span className="check-manual">{c.manual_verify}</span>
                      )}
                    </div>
                    <div className="check-actions">
                      {c.verify_url && (
                        <a
                          className="flyout"
                          href={c.verify_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Verify ↗
                        </a>
                      )}
                      {c.status === "manual" && (
                        <button
                          type="button"
                          className={`mark ${manualDone[c.id] ? "done" : ""}`}
                          onClick={() =>
                            setManualDone((d) => ({ ...d, [c.id]: !d[c.id] }))
                          }
                        >
                          {manualDone[c.id] ? "Signed off ✓" : "Mark signed off"}
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </article>

          {(report || liveChecks.length > 0) && (
            <section className="log-panel">
              <h3>Full run log</h3>
              <ul className="log-list">
                {(report?.checks ?? liveChecks).map((c) => (
                  <li key={`log-${c.id}`} className={`log-line status-${c.status}`}>
                    <span>{statusIcon(c.status)}</span>
                    <span className="log-phase">{c.phase}</span>
                    <span>{c.title}</span>
                    {c.verify_url && (
                      <a href={c.verify_url} target="_blank" rel="noreferrer">
                        ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
