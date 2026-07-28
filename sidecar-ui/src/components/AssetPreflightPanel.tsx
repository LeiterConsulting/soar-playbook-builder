import type { AssetPreflight, AssetRequirement } from "../types";

interface AssetPreflightPanelProps {
  preflight: AssetPreflight;
  selections: Record<string, string>;
  onChange: (key: string, assetName: string) => void;
  onConfirm: () => void;
  busy: boolean;
}

function statusLabel(req: AssetRequirement): string {
  switch (req.status) {
    case "resolved":
      if (req.resolution === "builtin_soar") {
        return "Built-in SOAR (add note / assign)";
      }
      return req.resolved_name
        ? `Mapped to ${req.resolved_name}`
        : req.resolution || "Ready";
    case "ambiguous":
      return "Choose a configured asset";
    case "missing":
      return "Not configured on SOAR";
    default:
      return req.resolution || req.status;
  }
}

export function AssetPreflightPanel({
  preflight,
  selections,
  onChange,
  onConfirm,
  busy,
}: AssetPreflightPanelProps) {
  const requirements = preflight.requirements || [];
  const blocked = requirements.some(
    (r) =>
      r.status === "missing" ||
      (r.status === "ambiguous" && !selections[r.key]) ||
      r.status === "invalid_override",
  );

  return (
    <div className="asset-preflight" aria-live="polite">
      <div className="asset-preflight-title">Integration check</div>
      <p className="asset-preflight-desc">
        SOAR needs configured assets before import so action blocks are not left unmapped.
      </p>
      <ul className="asset-preflight-list">
        {requirements.map((req) => (
          <li key={req.key} className={`asset-row ${req.status}`}>
            <div className="asset-row-head">
              <strong>{req.label || req.key}</strong>
              <span className="asset-row-status">{statusLabel(req)}</span>
            </div>
            {req.status === "ambiguous" && (req.candidates?.length || 0) > 0 && (
              <label className="asset-select-label">
                Use asset
                <select
                  value={selections[req.key] || ""}
                  onChange={(e) => onChange(req.key, e.target.value)}
                  disabled={busy}
                >
                  <option value="">Select…</option>
                  {(req.candidates || []).map((c) => (
                    <option key={c.name} value={c.name || ""}>
                      {c.name}
                      {c.product_name ? ` (${c.product_name})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {req.status === "missing" && (
              <p className="asset-row-hint">
                Add a {req.label || req.key} configuration under Apps → Assets, or set{" "}
                <code>asset_defaults</code> on the Playbook Builder asset.
              </p>
            )}
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="asset-preflight-confirm"
        disabled={busy || blocked}
        onClick={onConfirm}
      >
        {blocked ? "Resolve integrations to import" : "Import with mappings"}
      </button>
    </div>
  );
}
