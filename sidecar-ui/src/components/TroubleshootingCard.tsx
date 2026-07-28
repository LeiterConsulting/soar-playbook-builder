import type { TroubleshootingEntry } from "../types";

interface TroubleshootingCardProps {
  entry: TroubleshootingEntry;
  onDismiss?: () => void;
  onSearchRelated?: (query: string) => void;
}

function severityClass(severity: string): string {
  if (severity === "error") return "ts-severity-error";
  if (severity === "warn") return "ts-severity-warn";
  return "ts-severity-info";
}

export function TroubleshootingCard({
  entry,
  onDismiss,
  onSearchRelated,
}: TroubleshootingCardProps) {
  const copySteps = () => {
    const blob = [
      entry.title,
      "",
      `Symptom: ${entry.symptom}`,
      `Cause: ${entry.cause}`,
      "",
      "Fix:",
      ...entry.fix_steps.map((s, i) => `${i + 1}. ${s}`),
      "",
      `Verify: ${entry.verify}`,
    ].join("\n");
    void navigator.clipboard.writeText(blob);
  };

  return (
    <div className={`troubleshooting-card ${severityClass(entry.severity)}`}>
      <div className="ts-header">
        <strong>{entry.title}</strong>
        {onDismiss && (
          <button type="button" className="ts-dismiss" onClick={onDismiss} aria-label="Dismiss">
            ×
          </button>
        )}
      </div>
      {entry.symptom && (
        <p className="ts-symptom">
          <span className="ts-label">Symptom:</span> {entry.symptom}
        </p>
      )}
      {entry.cause && (
        <p className="ts-cause">
          <span className="ts-label">Cause:</span> {entry.cause}
        </p>
      )}
      {entry.fix_steps.length > 0 && (
        <ol className="ts-steps">
          {entry.fix_steps.map((step) => (
            <li key={step.slice(0, 40)}>{step}</li>
          ))}
        </ol>
      )}
      {entry.verify && (
        <p className="ts-verify">
          <span className="ts-label">Verify:</span> {entry.verify}
        </p>
      )}
      <div className="ts-actions">
        <button type="button" className="btn secondary ts-copy" onClick={copySteps}>
          Copy steps
        </button>
        {onSearchRelated && (
          <button
            type="button"
            className="btn secondary"
            onClick={() => onSearchRelated(entry.id.replace(/_/g, " "))}
          >
            More help
          </button>
        )}
      </div>
    </div>
  );
}
