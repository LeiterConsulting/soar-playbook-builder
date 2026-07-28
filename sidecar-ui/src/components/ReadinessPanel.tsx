import type { ReadinessReport } from "../types";

interface ReadinessPanelProps {
  readiness: ReadinessReport;
  onApplyFixes?: () => void;
  busy?: boolean;
}

function severityIcon(severity: string): string {
  if (severity === "error") return "✕";
  if (severity === "warn") return "!";
  return "✓";
}

export function ReadinessPanel({ readiness, onApplyFixes, busy }: ReadinessPanelProps) {
  const items = readiness.items || [];
  if (items.length === 0) return null;

  const fixable = readiness.auto_fix_count || 0;

  return (
    <div className="readiness-panel" aria-live="polite">
      <div className="readiness-head">
        <span className="readiness-title">Readiness</span>
        <span className={`readiness-badge${readiness.ready_for_import ? " ok" : ""}`}>
          {readiness.ready_for_import ? "Ready" : `${readiness.error_count || 0} issues`}
        </span>
      </div>
      <ul className="readiness-list">
        {items.map((item) => (
          <li key={item.id} className={`readiness-row ${item.severity}`}>
            <span className="readiness-icon" aria-hidden>
              {severityIcon(item.severity || "info")}
            </span>
            <div className="readiness-body">
              <strong>{item.title}</strong>
              <span className="readiness-cat">{item.category}</span>
              <p>{item.detail}</p>
            </div>
          </li>
        ))}
      </ul>
      {fixable > 0 && onApplyFixes && (
        <button
          type="button"
          className="btn secondary readiness-apply"
          disabled={busy}
          onClick={onApplyFixes}
        >
          Apply {fixable} auto-fix{fixable === 1 ? "" : "es"}
        </button>
      )}
    </div>
  );
}
