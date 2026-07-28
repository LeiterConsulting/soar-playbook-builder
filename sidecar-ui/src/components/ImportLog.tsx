import type { ImportStep } from "../types";

interface ImportLogProps {
  steps: ImportStep[];
  attempts?: string[];
  visible: boolean;
}

function statusIcon(status: ImportStep["status"]): string {
  switch (status) {
    case "done":
      return "✓";
    case "running":
      return "…";
    case "error":
      return "✕";
    case "skipped":
      return "–";
    case "warning":
      return "!";
    default:
      return "○";
  }
}

export function ImportLog({ steps, attempts, visible }: ImportLogProps) {
  if (!visible || steps.length === 0) return null;

  return (
    <div className="import-log" aria-live="polite">
      <div className="import-log-title">Import progress</div>
      <ul className="import-log-steps">
        {steps.map((step) => (
          <li key={step.id} className={`import-step ${step.status}`}>
            <span className="import-step-icon">{statusIcon(step.status)}</span>
            <span className="import-step-body">
              <span className="import-step-label">{step.label}</span>
              {step.detail && <span className="import-step-detail">{step.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
      {attempts && attempts.length > 0 && (
        <details className="import-log-technical">
          <summary>Technical log</summary>
          <pre>{attempts.join("\n")}</pre>
        </details>
      )}
    </div>
  );
}
