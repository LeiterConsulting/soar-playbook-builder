interface StatusPillProps {
  label: string;
  tone: "ok" | "warn" | "muted";
  title?: string;
}

export function StatusPill({ label, tone, title }: StatusPillProps) {
  return (
    <span className={`status-pill ${tone}`} title={title}>
      <span className={`status-dot ${tone}`} aria-hidden />
      {label}
    </span>
  );
}
