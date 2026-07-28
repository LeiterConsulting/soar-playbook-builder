import { CodePreview } from "./CodePreview";
import { PreviewBlockCard } from "./PreviewBlockCard";
import type { PreviewBlock } from "../types";

interface PreviewPanelProps {
  activeTab: "blocks" | "code";
  onTabChange: (tab: "blocks" | "code") => void;
  preview: PreviewBlock[];
  source: string;
}

export function PreviewPanel({
  activeTab,
  onTabChange,
  preview,
  source,
}: PreviewPanelProps) {
  const tabs = [
    { id: "blocks" as const, label: "Blocks" },
    { id: "code" as const, label: "Code" },
  ];

  return (
    <div className="preview-stack">
      <div className="preview-head">
        <div className="preview-head-row">
          <h2>Preview</h2>
        </div>
        <div className="preview-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`preview-tab${activeTab === t.id ? " active" : ""}`}
              onClick={() => onTabChange(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div
        id="panel-blocks"
        className={`preview-panel${activeTab === "blocks" ? " active" : ""}`}
      >
        <div id="preview-flow">
          {preview.length === 0 ? (
            <p className="preview-empty">Build or pick a template to see playbook blocks.</p>
          ) : (
            preview.map((b, i) => (
              <div key={`${b.type}-${b.label}-${i}`} className="vpe-block">
                <PreviewBlockCard block={b} />
                {i < preview.length - 1 && <div className="vpe-connector" />}
              </div>
            ))
          )}
        </div>
      </div>

      <div
        id="panel-code"
        className={`preview-panel${activeTab === "code" ? " active" : ""}`}
      >
        <CodePreview id="preview-code" className="code-preview" source={source} />
      </div>
    </div>
  );
}
