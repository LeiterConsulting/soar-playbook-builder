import type { PreviewBlock } from "../types";

interface FlowDiagramProps {
  preview: PreviewBlock[];
}

export function FlowDiagram({ preview }: FlowDiagramProps) {
  if (!preview.length) {
    return (
      <div className="diagram-empty">
        Generate a playbook to see the flow diagram.
      </div>
    );
  }

  const w = 260;
  const h = 72;
  const gap = 16;
  const totalH = preview.length * (h + gap) + 20;

  return (
    <svg viewBox={`0 0 ${w} ${totalH}`} role="img" className="flow-diagram">
      {preview.map((b, i) => {
        const y = 10 + i * (h + gap);
        const nodeType = b.type || "action";
        return (
          <g key={`${b.label}-${i}`}>
            <rect
              x={10}
              y={y}
              width={w - 20}
              height={h}
              rx={8}
              className={`diag-node ${nodeType}`}
            />
            <text x={20} y={y + 22} className="diag-text">
              {(b.summary || b.label || b.type || "Step").slice(0, 36)}
            </text>
            <text x={20} y={y + 40} className="diag-sub">
              {((b.detail || b.action || "") + "").slice(0, 42)}
            </text>
            {(b.app_label || b.app) && (
              <text x={20} y={y + 58} className="diag-sub">
                {b.app_label || b.app}
              </text>
            )}
            {i < preview.length - 1 && (
              <line
                x1={w / 2}
                y1={y + h}
                x2={w / 2}
                y2={y + h + gap}
                className="diag-line"
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}
