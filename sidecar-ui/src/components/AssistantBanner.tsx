import { useBuilder } from "../context/BuilderProvider";

/** Assistant persona banner on Build — case-linked import focus. */
export function AssistantBanner() {
  const b = useBuilder();
  if (b.personaMode !== "assistant") return null;

  return (
    <section className="assistant-banner app-section" aria-label="Assistant mode">
      <div className="app-section-body">
        <strong>Case Playbook Assistant</strong>
        <span className="assistant-banner-sub">
          {b.canRunOnContainer
            ? "Build and import from the linked case — coach suggestions load automatically."
            : "Add container_id to the URL or open from a utility playbook for case-linked import."}
        </span>
        {b.canRunOnContainer && (
          <div className="assistant-banner-actions">
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={b.busy || !b.draftReady}
              title={b.runDisabledReason}
              onClick={() => void b.handleRunOnContainer()}
            >
              Run on this case
            </button>
            <button
              type="button"
              className="btn secondary btn-sm"
              disabled={b.busy}
              onClick={() => void b.refreshCoachSuggest()}
            >
              Refresh suggestions
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
