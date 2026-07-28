import { useRef } from "react";
import { PreviewPanel } from "./PreviewPanel";
import { ActionBar } from "./ActionBar";
import { PaneResizeHandle } from "./PaneResizeHandle";
import { useResizablePaneHeight } from "../hooks/useResizablePaneHeight";
import type { PreviewBlock } from "../types";

interface PreviewColumnProps {
  variant: "build" | "run";
  activeTab: "blocks" | "code";
  onTabChange: (tab: "blocks" | "code") => void;
  preview: PreviewBlock[];
  source: string;
}

/** Right column: resizable preview stack + import/action footer. */
export function PreviewColumn({
  variant,
  activeTab,
  onTabChange,
  preview,
  source,
}: PreviewColumnProps) {
  const rightRef = useRef<HTMLDivElement>(null);
  const previewWrapRef = useRef<HTMLDivElement>(null);
  const { paneHeight, onPointerDown, resetHeight } = useResizablePaneHeight(
    rightRef,
    previewWrapRef,
    {
      storageKey: "pb-preview-panel-height",
      minPane: 56,
      minSibling: 100,
    },
  );

  return (
    <div className="right preview-right" ref={rightRef}>
      <div
        ref={previewWrapRef}
        className={`preview-stack-wrap${paneHeight != null ? " preview-stack-wrap-sized" : ""}`}
        style={paneHeight != null ? { height: paneHeight } : undefined}
      >
        <PreviewPanel
          activeTab={activeTab}
          onTabChange={onTabChange}
          preview={preview}
          source={source}
        />
      </div>
      <PaneResizeHandle
        orientation="horizontal"
        className="preview-resize-handle"
        ariaLabel="Drag to resize preview. Double-click to reset size."
        ariaValueNow={paneHeight ?? undefined}
        onPointerDown={onPointerDown}
        onDoubleClick={resetHeight}
      />
      <div
        className={`preview-action-footer${paneHeight != null ? " preview-action-footer-flex" : ""}`}
      >
        <ActionBar variant={variant} />
      </div>
    </div>
  );
}
