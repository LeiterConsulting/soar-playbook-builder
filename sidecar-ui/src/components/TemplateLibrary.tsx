import { useState } from "react";
import type { PatternDefinition } from "../patterns/registry";
import { WIZARD_SCENARIOS, type WizardScenario } from "../patterns/scenarios";

const TEMPLATES_COLLAPSED_KEY = "pb-templates-collapsed";

function readCollapsedPreference(): boolean {
  try {
    return localStorage.getItem(TEMPLATES_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export interface PatternCategoryGroup {
  category: string;
  patterns: PatternDefinition[];
}

interface TemplateLibraryProps {
  patterns: PatternDefinition[];
  byCategory?: Record<string, PatternDefinition[]>;
  orgTemplateCount?: number;
  value: string;
  onChange: (patternId: string) => void;
  onLoad: () => void;
  onValidate?: () => void;
  onUseScenarioPrompt?: (scenario: WizardScenario) => void;
  busy?: boolean;
  scoreLabel?: string;
}

function groupPatterns(
  patterns: PatternDefinition[],
  byCategory?: Record<string, PatternDefinition[]>,
): PatternCategoryGroup[] {
  if (byCategory && Object.keys(byCategory).length > 0) {
    return Object.entries(byCategory).map(([category, items]) => ({
      category,
      patterns: items,
    }));
  }
  return [{ category: "All templates", patterns }];
}

function integrationsFor(selected: PatternDefinition | undefined, scenario: WizardScenario | undefined): string[] {
  const fromPattern = selected?.integrations ?? [];
  const fromScenario = scenario?.integrations ?? [];
  return [...new Set([...fromPattern, ...fromScenario])];
}

function templateCountLabel(builtinCount: number, orgCount: number): string {
  if (orgCount > 0) {
    return `${builtinCount} built-in · ${orgCount} org`;
  }
  return `${builtinCount} built-in`;
}

export function TemplateLibrary({
  patterns,
  byCategory,
  orgTemplateCount = 0,
  value,
  onChange,
  onLoad,
  onValidate,
  onUseScenarioPrompt,
  busy,
  scoreLabel,
}: TemplateLibraryProps) {
  const [collapsed, setCollapsed] = useState(readCollapsedPreference);
  const groups = groupPatterns(patterns, byCategory);
  const selected = patterns.find((p) => p.id === value);
  const scenario = WIZARD_SCENARIOS.find((s) => s.pattern === value);
  const description = scenario?.description || selected?.description;
  const integrations = integrationsFor(selected, scenario);
  const builtinCount = patterns.filter((p) => !p.org).length;
  const orgCount =
    orgTemplateCount > 0 ? orgTemplateCount : patterns.filter((p) => p.org).length;
  const countLabel = templateCountLabel(builtinCount, orgCount);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(TEMPLATES_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore storage errors */
      }
      return next;
    });
  };

  return (
    <section
      className={`panel-section app-section template-library${collapsed ? " template-library--collapsed" : ""}`}
    >
      <div className="app-section-header template-library-header">
        <span className="template-library-title">Templates</span>
        <span className="template-library-count" title="Built-in starter patterns and organization templates from asset config">
          {countLabel}
        </span>
        <div className="template-library-header-actions">
          {collapsed && selected && (
            <span className="template-collapsed-label" title={selected.label}>
              {selected.label}
            </span>
          )}
          <button
            type="button"
            className="btn btn-ghost btn-sm section-collapse-btn"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-controls="template-library-body"
          >
            {collapsed ? "Expand" : "Collapse"}
          </button>
        </div>
      </div>
      {!collapsed && (
      <div className="app-section-body template-library-body" id="template-library-body">
        <div className="template-library-row">
          <select
            className="pattern-select template-select"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            aria-label="Playbook template"
            aria-describedby={selected ? "template-detail-panel" : undefined}
          >
            {groups.map((group) => (
              <optgroup key={group.category} label={group.category}>
                {group.patterns.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.org ? "[Org] " : ""}
                    {p.label}
                    {p.tier === "destructive" ? " ⚠" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <button
            type="button"
            className={`btn btn-primary${busy ? " busy" : ""}`}
            disabled={busy}
            onClick={onLoad}
          >
            Load template
          </button>
          {onValidate && (
            <button type="button" className="btn secondary" disabled={busy} onClick={onValidate}>
              Validate
            </button>
          )}
          {scoreLabel && <span className="score">{scoreLabel}</span>}
        </div>

        {selected && description && (
          <div className="template-detail" id="template-detail-panel" key={value}>
            <p className="template-detail-summary">{description}</p>

            <div className="template-detail-meta">
              {selected.org && <span className="template-badge org">Organization</span>}
              {selected.offline !== false && (
                <span className="template-badge offline">Works offline</span>
              )}
              {selected.tier === "destructive" && (
                <span className="template-badge warn">Destructive · lab only</span>
              )}
              {integrations.map((name) => (
                <span key={name} className="template-badge integration">
                  {name}
                </span>
              ))}
            </div>

            {scenario && scenario.steps.length > 0 && (
              <details className="template-detail-fold">
                <summary>Lab walkthrough · {scenario.steps.length} steps</summary>
                <ol className="template-detail-steps">
                  {scenario.steps.map((step) => (
                    <li key={step.id}>
                      <strong>{step.title}</strong>
                      <span>{step.detail}</span>
                    </li>
                  ))}
                </ol>
              </details>
            )}

            {scenario?.examplePrompt && onUseScenarioPrompt && (
              <details className="template-detail-fold">
                <summary>Example natural language prompt</summary>
                <p className="template-detail-prompt">{scenario.examplePrompt}</p>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => onUseScenarioPrompt(scenario)}
                >
                  Use in chat
                </button>
              </details>
            )}

            {!scenario && selected.integrations && selected.integrations.length > 0 && (
              <details className="template-detail-fold">
                <summary>Integrations</summary>
                <p className="template-detail-copy">
                  Requires configured SOAR assets: {selected.integrations.join(", ")}. Set{" "}
                  <code>asset_defaults</code> on the Playbook Builder asset or map at import.
                </p>
              </details>
            )}
          </div>
        )}

        <p className="template-library-footnote">
          {orgCount > 0 ? (
            <>
              Includes <strong>{orgCount}</strong> organization template
              {orgCount === 1 ? "" : "s"} from asset <code>custom_templates_json</code>.
            </>
          ) : (
            <>
              Starter set — admins can add org templates on the asset (
              <code>custom_templates_json</code>) without rebuilding the app.
            </>
          )}{" "}
          Help → <strong>Growing &amp; Customizing Templates</strong>.
        </p>
      </div>
      )}
    </section>
  );
}
