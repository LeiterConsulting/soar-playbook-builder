import type { WizardScenario } from "../patterns/scenarios";
import { WIZARD_SCENARIOS } from "../patterns/scenarios";

interface WizardPanelProps {
  activeId: string | null;
  onSelect: (scenario: WizardScenario) => void;
  onStart: (scenario: WizardScenario) => void;
  onUsePrompt?: (scenario: WizardScenario) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function WizardPanel({
  activeId,
  onSelect,
  onStart,
  onUsePrompt,
  collapsed,
  onToggleCollapse,
}: WizardPanelProps) {
  const active = WIZARD_SCENARIOS.find((s) => s.id === activeId) ?? null;

  return (
    <div className={`wizard-panel${collapsed ? " collapsed" : ""}`}>
      <div className="wizard-head app-section-header">
        <span>Wizard</span>
        {onToggleCollapse && (
          <button type="button" className="btn secondary wizard-toggle" onClick={onToggleCollapse}>
            {collapsed ? "Show" : "Hide"}
          </button>
        )}
      </div>
      {!collapsed && (
        <>
          <div className="wizard-scenarios">
            {WIZARD_SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`wizard-chip${activeId === s.id ? " active" : ""}`}
                onClick={() => onSelect(s)}
                title={s.description}
              >
                {s.label}
              </button>
            ))}
          </div>
          {active && (
            <div className="wizard-detail">
              <p className="wizard-desc">{active.description}</p>
              {active.integrations.length > 0 && (
                <p className="wizard-integrations">
                  <span className="ts-label">Integrations:</span>{" "}
                  {active.integrations.join(", ")}
                </p>
              )}
              <ol className="wizard-steps">
                {active.steps.map((step) => (
                  <li key={step.id}>
                    <strong>{step.title}</strong>
                    <span>{step.detail}</span>
                  </li>
                ))}
              </ol>
              <div className="wizard-actions">
                <button
                  type="button"
                  className="btn btn-primary wizard-start"
                  onClick={() => onStart(active)}
                >
                  Start: {active.label}
                </button>
                {onUsePrompt && active.examplePrompt ? (
                  <button
                    type="button"
                    className="btn secondary"
                    title="Load NL prompt into chat (use Build when AI is connected)"
                    onClick={() => onUsePrompt(active)}
                  >
                    Use in chat
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
