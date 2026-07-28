import { useCallback, useEffect, useMemo, useState } from "react";
import { createApiClient, readUrlContext, resolveHandlerBase } from "../api";
import type { CaseSummary } from "../types";

interface CasePickerProps {
  linkedCaseId?: string;
  onLink: (caseRow: CaseSummary) => void;
  onProvisionDemo?: (caseRow: CaseSummary) => void;
  provisioningId?: string;
  compact?: boolean;
}

function severityClass(severity?: string): string {
  const s = (severity || "").toLowerCase();
  if (s === "critical") return "sev-critical";
  if (s === "high") return "sev-high";
  if (s === "medium") return "sev-medium";
  if (s === "low") return "sev-low";
  return "sev-unknown";
}

function tierLabel(tier?: string): string | null {
  if (tier === "destructive") return "lab only";
  if (tier === "integration") return "integration";
  if (tier === "safe") return "safe demo";
  return null;
}

/** Browse recent SOAR cases and built-in sample demos for run-on-case workflow. */
export function CasePicker({
  linkedCaseId,
  onLink,
  onProvisionDemo,
  provisioningId,
  compact = false,
}: CasePickerProps) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const api = createApiClient({
        handlerBase: resolveHandlerBase(),
        getPattern: () => "",
        getLinkedPlaybookId: () => "",
        getContextPlaybookId: () => "",
        getUrlContext: () => readUrlContext(),
      });
      const data = await api.apiGet({ action: "list_cases" });
      if (data.status === "error" && data.error) {
        setError(data.error);
        setCases([]);
      } else {
        setCases(data.cases || []);
        if (data.error_detail && !data.live_count) {
          setError(String(data.error_detail));
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const needle = filter.trim().toLowerCase();
  const filtered = needle
    ? cases.filter((c) => {
        const hay = [
          c.name,
          c.summary,
          c.rule_name,
          c.label,
          c.fixture_pattern_id,
          String(c.id),
          c.severity,
          c.source,
          c.demo_tier,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return hay.includes(needle);
      })
    : cases;

  const samples = useMemo(
    () => filtered.filter((c) => c.source === "sample"),
    [filtered],
  );
  const liveCases = useMemo(
    () => filtered.filter((c) => c.source !== "sample"),
    [filtered],
  );

  const renderRow = (row: CaseSummary) => {
    const id = String(row.id);
    const linked = linkedCaseId === id;
    const isSample = row.source === "sample";
    const tier = tierLabel(row.demo_tier);

    return (
      <li key={id} className={`case-picker-row${linked ? " linked" : ""}${isSample ? " sample-row" : ""}`}>
        <div className="case-picker-main">
          <div className="case-picker-title">
            <span className={`case-severity ${severityClass(row.severity)}`}>
              {(row.severity || "—").toUpperCase()}
            </span>
            <strong>{row.name}</strong>
            {isSample && <span className="case-badge sample">sample</span>}
            {row.showcase_recommended && (
              <span className="case-badge showcase">demo pick</span>
            )}
            {tier && <span className={`case-badge tier-${row.demo_tier}`}>{tier}</span>}
            {linked && <span className="case-badge linked">linked</span>}
          </div>
          <div className="case-picker-meta">
            <span>Case {id}</span>
            {row.fixture_pattern_id && <span>template {row.fixture_pattern_id}</span>}
            {row.rule_name && <span>{row.rule_name}</span>}
            {row.status && <span>{row.status}</span>}
          </div>
          {row.summary && <p className="case-picker-summary">{row.summary}</p>}
        </div>
        <div className="case-picker-actions">
          {isSample && onProvisionDemo && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={provisioningId === id}
              onClick={() => onProvisionDemo(row)}
            >
              {provisioningId === id ? "Creating…" : "Create on SOAR"}
            </button>
          )}
          {!isSample && (
            <button
              type="button"
              className={`btn${linked ? " secondary" : " btn-primary"}`}
              disabled={linked}
              onClick={() => onLink(row)}
            >
              {linked ? "Linked" : "Link"}
            </button>
          )}
        </div>
      </li>
    );
  };

  return (
    <details className={`case-picker app-section${compact ? " case-picker-compact" : ""}`} open={!compact}>
      <summary>{linkedCaseId ? `Case ${linkedCaseId}` : "Cases"}</summary>
      <div className="case-picker-body">
        <p className="case-picker-demo-note">
          Sample cases are for demos — use <strong>Create on SOAR</strong> (not Link) so Run on this
          case works against a real container with artifacts.
        </p>
        <div className="case-picker-toolbar">
          <input
            type="search"
            className="case-picker-search"
            placeholder="Filter…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter cases"
          />
          <button type="button" className="btn secondary case-picker-refresh" onClick={() => void loadCases()}>
            Refresh
          </button>
        </div>
        {loading && <p className="case-picker-status">Loading…</p>}
        {!loading && error && (
          <p className="case-picker-status case-picker-error">{error}</p>
        )}
        {!loading && filtered.length === 0 && (
          <p className="case-picker-status">No matches.</p>
        )}
        {!loading && samples.length > 0 && (
          <>
            <h3 className="case-picker-group-title">Demo samples</h3>
            <ul className="case-picker-list case-picker-list-samples">{samples.map(renderRow)}</ul>
          </>
        )}
        {!loading && liveCases.length > 0 && (
          <>
            <h3 className="case-picker-group-title">Live SOAR cases</h3>
            <ul className="case-picker-list">{liveCases.map(renderRow)}</ul>
          </>
        )}
      </div>
    </details>
  );
}
