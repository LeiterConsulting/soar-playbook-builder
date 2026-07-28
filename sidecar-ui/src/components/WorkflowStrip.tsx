export type WorkflowStep = 1 | 2 | 3 | 4;

interface WorkflowStripProps {
  activeStep: WorkflowStep;
}

const STEPS: { step: WorkflowStep; label: string }[] = [
  { step: 1, label: "Template" },
  { step: 2, label: "Preview" },
  { step: 3, label: "Import" },
  { step: 4, label: "Run" },
];

export function WorkflowStrip({ activeStep }: WorkflowStripProps) {
  return (
    <nav className="workflow-strip" aria-label="Playbook build workflow">
      <ol className="workflow-track">
        {STEPS.map(({ step, label }, index) => {
          const done = activeStep > step;
          const active = activeStep === step;
          return (
            <li
              key={step}
              className={`workflow-step${done ? " done" : ""}${active ? " active" : ""}`}
              aria-current={active ? "step" : undefined}
            >
              <span className="workflow-marker">{done ? "✓" : step}</span>
              <span className="workflow-label">{label}</span>
              {index < STEPS.length - 1 && <span className="workflow-connector" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
