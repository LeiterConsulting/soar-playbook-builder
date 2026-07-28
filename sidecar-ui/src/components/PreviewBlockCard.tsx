import type { PreviewBlock } from "../types";

const TYPE_LABELS: Record<string, string> = {
  start: "Start",
  collect: "Collect",
  action: "Action",
  decision: "Decision",
  note: "Note",
  end: "Finish",
};

const TYPE_HINTS: Record<string, string> = {
  start: "Entry point when the playbook runs on a container",
  collect: "Reads artifact or case fields into playbook variables",
  action: "Calls a SOAR app connector on a configured asset",
  decision: "Branches the flow based on severity, posture, or action results",
  note: "Adds context to the case timeline for analysts",
  end: "Closes the playbook run",
};

function splitPipe(value?: string): string[] {
  if (!value) return [];
  return value.split("|").map((s) => s.trim()).filter(Boolean);
}

function blockTitle(block: PreviewBlock): string {
  if (block.summary) return block.summary;
  if (block.type === "action" && block.action) {
    return block.action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return block.label || TYPE_LABELS[block.type || ""] || "Step";
}

interface PreviewBlockCardProps {
  block: PreviewBlock;
}

export function PreviewBlockCard({ block }: PreviewBlockCardProps) {
  const nodeType = block.type || "action";
  const typeLabel = TYPE_LABELS[nodeType] || nodeType;
  const typeHint = TYPE_HINTS[nodeType] || "";
  const title = blockTitle(block);
  const fieldLabels = splitPipe(block.fields);
  const rawPaths = splitPipe(block.datapaths);

  return (
    <div className={`vpe-card ${nodeType}`}>
      <div className="vpe-card-head">
        <span className="type-pill">{typeLabel}</span>
        {typeHint && (
          <button
            type="button"
            className="type-hint"
            data-hint={typeHint}
            aria-label={`About ${typeLabel} blocks: ${typeHint}`}
            onClick={(e) => {
              e.currentTarget.classList.toggle("show-hint");
            }}
          >
            ?
          </button>
        )}
      </div>
      <div className="title">{title}</div>
      {block.detail && <div className="detail">{block.detail}</div>}

      {fieldLabels.length > 0 && (
        <ul className="vpe-field-list" aria-label="Collected fields">
          {fieldLabels.map((field, idx) => (
            <li key={`${field}-${idx}`}>
              <span className="vpe-field-name">{field}</span>
              {rawPaths[idx] && (
                <span className="vpe-field-path" title={rawPaths[idx]}>
                  {rawPaths[idx]}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {block.type === "action" && block.action && (
        <div className="vpe-meta-row">
          <span className="vpe-meta-label">Action</span>
          <code className="vpe-meta-value">{block.action}</code>
        </div>
      )}

      {block.callback && (
        <div className="vpe-meta-row">
          <span className="vpe-meta-label">Next</span>
          <span className="vpe-meta-value">{block.callback.replace(/_/g, " ")}</span>
        </div>
      )}

      {(block.app_label || block.app) && (
        <div className="app-badge">{block.app_label || block.app}</div>
      )}
    </div>
  );
}
