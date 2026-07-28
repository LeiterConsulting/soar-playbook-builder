import { useBuilder } from "../context/BuilderProvider";
import { navigateToRoute } from "../navigation";

export function CoachRespondPanel() {
  const b = useBuilder();
  const suggest = b.coachSuggest;
  const loading = b.coachLoading;
  const intel = suggest?.case_intel as { run_count?: number; recent_runs?: unknown[] } | undefined;

  return (
    <section className="app-section coach-respond-panel">
      <div className="app-section-header">Respond on this case</div>
      <div className="app-section-body">
        {loading && <p className="coach-status">Loading coach suggestions…</p>}
        {!loading && suggest?.content && (
          <div className="coach-respond-body">{formatCoachText(suggest.content)}</div>
        )}
        {!loading && !suggest?.content && (
          <p className="coach-status">
            Link a case via ES drilldown, Splunk <code>splunk_link</code>, utility playbook, or{" "}
            <code>container_id</code> in the URL for template suggestions.
          </p>
        )}
        {!loading && intel?.run_count ? (
          <p className="coach-status coach-intel-hint">
            {intel.run_count} recent playbook run(s) on this case — import a template then run from
            Build or Studio Run tab.
          </p>
        ) : null}
        <div className="coach-respond-actions">
          {suggest?.suggested_pattern && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={b.busy}
              onClick={() => {
                b.setCurrentPattern(String(suggest.suggested_pattern));
                void b.handleScaffold();
                b.setCoachTab("build");
              }}
            >
              Load suggested template
            </button>
          )}
          {b.canRunOnContainer && (
            <button
              type="button"
              className="btn secondary"
              disabled={b.busy || !b.draftReady}
              title={b.runDisabledReason}
              onClick={() => void b.handleRunOnContainer()}
            >
              Run on this case
            </button>
          )}
          {b.personaMode === "studio" && b.canRunOnContainer && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => navigateToRoute("run")}
            >
              Open Run tab
            </button>
          )}
          <button type="button" className="btn secondary" onClick={() => b.setCoachTab("explain")}>
            Explain playbook concepts
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => b.setCoachTab("build")}>
            Open Build lane
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={b.coachLoading}
            onClick={() => void b.refreshCoachSuggest()}
          >
            Refresh
          </button>
        </div>
      </div>
    </section>
  );
}

function formatCoachText(text: string) {
  return text.split("\n").map((line, i) => {
    const key = `${line.slice(0, 24)}-${i}`;
    if (line.startsWith("**") && line.endsWith("**")) {
      return (
        <p key={key} className="coach-line coach-line-strong">
          {line.slice(2, -2)}
        </p>
      );
    }
    if (!line.trim()) return <br key={key} />;
    return (
      <p key={key} className="coach-line">
        {line}
      </p>
    );
  });
}
