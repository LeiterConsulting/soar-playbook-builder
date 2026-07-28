import { useCallback, useEffect, useRef, useState } from "react";
import type { BuilderResponse } from "../types";

interface EnvCheck extends BuilderResponse {
  checks?: Array<{ id: string; severity: string; title: string; detail: string }>;
  fixes?: Array<{ id: string; label: string; action?: string; hint?: string; auto?: boolean }>;
  nl_mode?: string;
  nl_ready?: boolean;
  suggested_asset_defaults?: Record<string, string>;
}

interface EnvironmentMenuProps {
  apiGet: (qs: Record<string, string | undefined>) => Promise<BuilderResponse>;
  bridgeOk: boolean | null;
  bridgeLabel: string;
  bridgeTone: "ok" | "warn" | "muted";
  onRetryBridge: () => void | Promise<void>;
  onUseTemplate: (patternId: string) => void;
  onFixEnvironment?: () => Promise<void>;
  onRunSetupAction?: (action: string) => Promise<void>;
  fixing?: boolean;
  suggestedPattern?: string;
  refreshToken?: number;
}

function formatCheckedAt(d: Date): string {
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

/** Header dropdown for MCP bridge + integration readiness (all tabs). */
export function EnvironmentMenu({
  apiGet,
  bridgeOk,
  bridgeLabel,
  bridgeTone,
  onRetryBridge,
  onUseTemplate,
  onFixEnvironment,
  onRunSetupAction,
  fixing = false,
  suggestedPattern,
  refreshToken = 0,
}: EnvironmentMenuProps) {
  const [open, setOpen] = useState(false);
  const [env, setEnv] = useState<EnvCheck | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      await Promise.resolve(onRetryBridge());
      const data = (await apiGet({
        action: "environment_check",
        _ts: String(Date.now()),
      })) as EnvCheck;
      setEnv(data);
      setLastChecked(new Date());
    } catch {
      setRefreshError("Could not refresh status. Check your SOAR session and try again.");
    } finally {
      setRefreshing(false);
    }
  }, [apiGet, onRetryBridge]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshToken]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const bridgeDown = bridgeOk === false;
  const llmMissing = bridgeOk === true && env?.llm_configured === false;
  const defaultsOpen = env?.checks?.some(
    (c) => c.id === "asset_defaults" && c.severity !== "ok",
  );
  const canFixDefaults =
    defaultsOpen &&
    Boolean(env?.suggested_asset_defaults && Object.keys(env.suggested_asset_defaults).length);
  const needsAttention = bridgeDown || llmMissing || canFixDefaults || (env != null && !env.nl_ready);

  const pattern = suggestedPattern || "hello";
  const fixHint =
    env?.suggested_asset_defaults &&
    Object.entries(env.suggested_asset_defaults)
      .slice(0, 4)
      .map(([k, v]) => `${k} → ${v}`)
      .join(" · ");

  return (
    <div className="env-menu" ref={rootRef}>
      <button
        type="button"
        className={`env-menu-trigger${needsAttention ? " needs-attention" : ""}${open ? " open" : ""}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        title="MCP bridge, asset defaults, and NL readiness"
      >
        <span className={`status-dot ${bridgeTone}`} aria-hidden />
        <span className="env-menu-trigger-label">{bridgeLabel}</span>
        {needsAttention && <span className="env-menu-attention-dot" aria-hidden />}
        <span className="env-menu-chevron" aria-hidden>
          ▾
        </span>
      </button>

      {open && (
        <div className="env-menu-panel" role="dialog" aria-label="Environment status">
          <div className="env-menu-panel-head">
            <strong>Environment</strong>
            <div className="env-menu-panel-meta">
              {lastChecked && !refreshing && (
                <span className="env-last-checked">Updated {formatCheckedAt(lastChecked)}</span>
              )}
              <button
                type="button"
                className={`btn btn-ghost btn-sm${refreshing ? " busy" : ""}`}
                disabled={refreshing || fixing}
                onClick={() => void refresh()}
              >
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          </div>

          <div className="env-menu-panel-body">
            {refreshing && !env ? (
              <p className="env-loading">Checking environment…</p>
            ) : (
              <>
                {env?.message && <p className="env-summary">{env.message}</p>}
                {refreshError && <p className="env-refresh-error">{refreshError}</p>}
                {env?.checks && env.checks.length > 0 && (
                  <ul className="env-check-list">
                    {env.checks.map((c) => (
                      <li key={c.id} className={`env-check-row env-sev-${c.severity}`}>
                        <span className={`env-check-dot env-dot-${c.severity}`} aria-hidden />
                        <div className="env-check-copy">
                          <span className="env-check-title">{c.title}</span>
                          <span className="env-check-detail">{c.detail}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {canFixDefaults && fixHint && (
                  <p className="env-fix-hint">
                    <span className="env-fix-label">Suggested mapping</span> {fixHint}
                  </p>
                )}
                <div className="env-actions">
                  {env?.fixes
                    ?.filter(
                      (f) =>
                        f.action &&
                        f.action !== "apply_environment_fixes" &&
                        f.action !== "use_template" &&
                        f.action !== "provision_demo_case",
                    )
                    .map((fix) => (
                      <button
                        key={fix.id}
                        type="button"
                        className="btn secondary"
                        disabled={fixing || refreshing}
                        title={fix.hint}
                        onClick={() => {
                          if (fix.action && onRunSetupAction) void onRunSetupAction(fix.action);
                        }}
                      >
                        {fix.label}
                      </button>
                    ))}
                  {canFixDefaults && onFixEnvironment && (
                    <button
                      type="button"
                      className={`btn btn-accent${fixing ? " busy" : ""}`}
                      disabled={fixing || refreshing}
                      onClick={() => void onFixEnvironment()}
                    >
                      {fixing ? "Applying…" : "Fix environment"}
                    </button>
                  )}
                  {bridgeDown && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={refreshing}
                      onClick={() => {
                        onUseTemplate(pattern);
                        setOpen(false);
                      }}
                    >
                      Use template
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
