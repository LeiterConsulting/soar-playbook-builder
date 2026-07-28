interface RunOnCaseHelpProps {
  hasCase: boolean;
  hasImportedPlaybook: boolean;
  hasDraft?: boolean;
  caseId?: string;
  playbookId?: string;
  defaultOpen?: boolean;
}

export function RunOnCaseHelp({
  hasCase,
  hasImportedPlaybook,
  hasDraft = false,
  caseId,
  playbookId,
  defaultOpen = false,
}: RunOnCaseHelpProps) {
  const ready = hasCase && hasImportedPlaybook;

  return (
    <details className="run-on-case-help app-section" open={defaultOpen && !ready}>
      <summary>Help — why are buttons disabled?</summary>
      <div className="run-on-case-help-body">
        {ready ? (
          <p className="run-hint run-hint-ready">
            Ready — run playbook {playbookId} on case {caseId}.
          </p>
        ) : (
          <>
            <p className="run-hint">
              Linking a case alone does not enable Readiness or Run. Follow this order:
            </p>
            <ol className="run-on-case-steps">
              <li className={hasDraft ? "done" : ""}>
                <strong>Build</strong> → Templates → <em>Load template</em> (creates a draft)
              </li>
              <li className={hasDraft ? "done" : ""}>
                Optional: <strong>Readiness</strong> (checks Python &amp; integrations before import)
              </li>
              <li className={hasImportedPlaybook ? "done" : ""}>
                <strong>Build</strong> → <em>Import to SOAR</em>
              </li>
              <li className={hasCase ? "done" : ""}>
                <strong>Run</strong> → link a case (picker, ES drilldown, or{" "}
                <code>container_id</code> in URL)
              </li>
              <li>
                <strong>Run on this case</strong>
              </li>
            </ol>
            {!hasDraft && (
              <p className="run-hint run-hint-blocked">
                Readiness is waiting for a draft — load a template on Build first.
              </p>
            )}
            {hasDraft && !hasImportedPlaybook && (
              <p className="run-hint run-hint-blocked">Draft loaded — import to SOAR on Build.</p>
            )}
            {!hasCase && hasImportedPlaybook && (
              <p className="run-hint run-hint-blocked">Playbook imported — link a case above.</p>
            )}
            {hasCase && !hasImportedPlaybook && (
              <p className="run-hint run-hint-blocked">
                Case {caseId} linked — import a playbook on Build before Run.
              </p>
            )}
          </>
        )}
      </div>
    </details>
  );
}
