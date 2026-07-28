import { ImportLog } from "./ImportLog";
import { AssetPreflightPanel } from "./AssetPreflightPanel";
import { ReadinessPanel } from "./ReadinessPanel";
import { TroubleshootingCard } from "./TroubleshootingCard";
import { useBuilder } from "../context/BuilderProvider";

interface ActionBarProps {
  variant: "build" | "run";
}

export function ActionBar({ variant }: ActionBarProps) {
  const b = useBuilder();

  return (
    <div className="soar-links action-bar">
      <div className="action-bar-head">
        <span className="step-badge">{b.workflowStep >= 3 ? 3 : 2}</span>
        <span className="action-bar-title">{b.linkedPlaybookId ? "Imported" : "Import"}</span>
      </div>
      <div className="action-bar-buttons">
        {b.syncStatus.kind === "ok" && <span className="sync-ok">{b.syncStatus.message}</span>}
        {b.syncStatus.kind === "error" && <span className="sync-err">{b.syncStatus.message}</span>}
        {b.troubleshooting && b.syncStatus.kind === "error" && (
          <TroubleshootingCard entry={b.troubleshooting} onDismiss={() => b.setTroubleshooting(null)} />
        )}
        {b.syncStatus.kind === "pending" && (
          <span className="sync-pending">{b.syncStatus.message}</span>
        )}
        <ImportLog steps={b.importSteps} attempts={b.importAttempts} visible={b.showImportLog} />
        {b.showAssetPanel && b.assetPreflight && (
          <AssetPreflightPanel
            preflight={b.assetPreflight}
            selections={b.assetSelections}
            onChange={(key, assetName) =>
              b.setAssetSelections((prev) => ({ ...prev, [key]: assetName }))
            }
            onConfirm={() => void b.handleAssetConfirm()}
            busy={b.busy}
          />
        )}
        {b.readiness && (
          <ReadinessPanel
            readiness={b.readiness}
            onApplyFixes={
              (b.readiness.auto_fix_count || 0) > 0
                ? () => void b.handleApplyReadinessFixes()
                : undefined
            }
            busy={b.busy}
          />
        )}
        {variant === "build" && (
          <>
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
              className={`btn btn-primary${b.busy ? " busy" : ""}`}
              disabled={!b.draftReady || b.busy}
              title={b.draftReady ? "Import draft into SOAR" : "Load a template and preview it first"}
              onClick={() => void b.handleImport()}
            >
              {b.syncStatus.kind === "pending" ? "Importing…" : "Import to SOAR"}
            </button>
          </>
        )}
        {variant === "build" && (
          <button
            type="button"
            className={`btn btn-run${b.busy ? " busy" : ""}${b.canRunOnContainer ? "" : " disabled-visual"}`}
            disabled={!b.canRunOnContainer || b.busy}
            title={b.runDisabledReason}
            onClick={() => void b.handleRunOnContainer()}
          >
            Run on this case
          </button>
        )}
        {b.linkedPlaybookId ? (
          <a
            className="btn btn-open"
            href={b.openHref}
            target="_blank"
            rel="noopener noreferrer"
            title={`Open in Visual Editor (${b.linkedPlaybookSlug || b.linkedPlaybookId})`}
          >
            Open in SOAR
          </a>
        ) : (
          <button
            type="button"
            className="btn secondary"
            disabled
            title="Import first"
          >
            Open in SOAR
          </button>
        )}
      </div>
    </div>
  );
}
