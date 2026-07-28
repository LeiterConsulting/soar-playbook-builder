interface RunDemoGuideProps {
  hasImportedPlaybook: boolean;
  linkedCaseId?: string;
  onProvisionSample?: (sampleId: number) => void;
  provisioning?: boolean;
}

/** Run tab quick-start for built-in sample cases (9001–9005). */
export function RunDemoGuide({
  hasImportedPlaybook,
  linkedCaseId,
  onProvisionSample,
  provisioning,
}: RunDemoGuideProps) {
  const linked = Boolean(linkedCaseId);

  return (
    <details className="run-demo-guide app-section" open>
      <summary>Demo Showcase</summary>
      <div className="app-section-body run-demo-guide-body">
        <p className="run-demo-guide-lead">
          Built-in <strong>sample cases</strong> (9001–9005) ship with the app. They are not real SOAR
          containers until you click <strong>Create on SOAR</strong> — that provisions a case +
          artifacts for Run on this case.
        </p>
        <ol className="run-demo-guide-steps">
          <li>
            <strong>Build</strong> — load a template (recommended:{" "}
            <code>phishing-enrichment</code>, <code>es-notable-response</code>, or{" "}
            <code>hello</code>) and <strong>Import to SOAR</strong>.
          </li>
          <li>
            <strong>Run</strong> — expand <strong>Cases</strong>, pick a sample marked{" "}
            <span className="case-badge showcase">demo pick</span>, click{" "}
            <strong>Create on SOAR</strong>.
          </li>
          <li>
            <strong>Readiness</strong> → <strong>Run on this case</strong>.
          </li>
        </ol>
        {!hasImportedPlaybook && (
          <p className="run-demo-guide-hint run-demo-guide-hint-warn">
            Import a playbook on the Build tab first.
          </p>
        )}
        {hasImportedPlaybook && !linked && onProvisionSample && (
          <div className="run-demo-guide-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={provisioning}
              onClick={() => onProvisionSample(9005)}
            >
              {provisioning ? "Creating…" : "Quick demo: Hello case (9005)"}
            </button>
            <button
              type="button"
              className="btn secondary"
              disabled={provisioning}
              onClick={() => onProvisionSample(9002)}
            >
              Phishing case (9002)
            </button>
          </div>
        )}
        {linked && (
          <p className="run-demo-guide-hint run-demo-guide-hint-ok">
            Case {linkedCaseId} linked — run Readiness, then Run on this case.
          </p>
        )}
      </div>
    </details>
  );
}
