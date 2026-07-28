import { useRef, type CSSProperties } from "react";
import { CasePicker } from "../components/CasePicker";
import { ReadinessPanel } from "../components/ReadinessPanel";
import { RunDemoGuide } from "../components/RunDemoGuide";
import { RunOnCaseHelp } from "../components/RunOnCaseHelp";
import { PreviewColumn } from "../components/PreviewColumn";
import { useBuilder } from "../context/BuilderProvider";
import { PaneResizeHandle } from "../components/PaneResizeHandle";
import { useResizableSplitPane } from "../hooks/useResizableSplitPane";
import { demoSampleById } from "../demoSamples";

/** Run-on-case focused view with readiness and preview summary. */
export function RunPage() {
  const b = useBuilder();
  const layoutRef = useRef<HTMLDivElement>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const { leftPercent, onPointerDown: onSplitResize, resetSplit } = useResizableSplitPane(
    layoutRef,
    leftRef,
  );

  const layoutStyle =
    leftPercent != null
      ? ({ ["--split-left" as string]: `${leftPercent}%` } as CSSProperties)
      : undefined;

  return (
    <div
      ref={layoutRef}
      className={`layout run-page${leftPercent != null ? " layout-split-sized" : ""}`}
      style={layoutStyle}
    >
      <div className="left run-page-main" ref={leftRef}>
        <div className="run-stack">
          <RunDemoGuide
            hasImportedPlaybook={b.hasImportedPlaybook}
            linkedCaseId={b.urlCtx.containerId}
            provisioning={Boolean(b.provisioningCaseId)}
            onProvisionSample={(sampleId) => {
              const row = demoSampleById(sampleId);
              if (row) void b.provisionDemoCase(row);
            }}
          />
          <CasePicker
            linkedCaseId={b.urlCtx.containerId}
            onLink={(row) => b.linkCase(row)}
            onProvisionDemo={(row) => b.provisionDemoCase(row)}
            provisioningId={b.provisioningCaseId}
          />
          <div className="app-section">
            <div className="app-section-header">Actions</div>
            <div className="run-page-actions">
              <button
                type="button"
                className="btn secondary"
                disabled={b.busy || !b.canRunReadiness}
                title={b.readinessDisabledReason}
                onClick={() => void b.handleReadinessCheck()}
              >
                Readiness
              </button>
              <button
                type="button"
                className={`btn btn-run${b.busy ? " busy" : ""}${b.canRunOnContainer || b.usingMocks ? "" : " disabled-visual"}`}
                disabled={(!b.canRunOnContainer && !b.usingMocks) || b.busy}
                title={b.runDisabledReason}
                onClick={() => void b.handleRunOnContainer()}
              >
                Run on this case
              </button>
            </div>
            <p className="run-actions-hint">
              {!b.draftReady
                ? "Readiness needs a draft — Build tab → Templates → Load template (then Import)."
                : !b.hasImportedPlaybook
                  ? "Draft loaded — Import to SOAR on Build before Run."
                  : !b.urlCtx.containerId
                    ? "Playbook linked — pick a case above (or use ES drilldown)."
                    : "Case and playbook ready — run Readiness, then Run on this case."}
            </p>
          </div>
          {b.readiness && (
            <div className="app-section">
              <div className="app-section-header">Readiness</div>
              <ReadinessPanel
                readiness={b.readiness}
                onApplyFixes={
                  (b.readiness.auto_fix_count || 0) > 0
                    ? () => void b.handleApplyReadinessFixes()
                    : undefined
                }
                busy={b.busy}
              />
            </div>
          )}
          <RunOnCaseHelp
            hasCase={Boolean(b.urlCtx.containerId) || b.usingMocks}
            hasImportedPlaybook={b.hasImportedPlaybook}
            hasDraft={b.draftReady}
            caseId={b.urlCtx.containerId || (b.usingMocks ? "9001" : undefined)}
            playbookId={b.linkedPlaybookId || b.urlCtx.contextPlaybookId}
            defaultOpen={Boolean(b.urlCtx.containerId) && !b.hasImportedPlaybook}
          />
        </div>
      </div>

      <PaneResizeHandle
        orientation="vertical"
        ariaLabel="Drag to widen left column. Double-click to reset width."
        ariaValueNow={leftPercent ?? undefined}
        onPointerDown={onSplitResize}
        onDoubleClick={resetSplit}
      />

      <PreviewColumn
        variant="run"
        activeTab="blocks"
        onTabChange={() => {}}
        preview={b.preview}
        source={b.currentSource}
      />
    </div>
  );
}
