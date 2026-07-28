import { InvestigationContext } from "../types";

interface EsBackLinkProps {
  investigationContext: InvestigationContext | null;
  eventId?: string;
}

/** Header link back to ES Mission Control when event_id / es_links are present. */
export function EsBackLink({ investigationContext, eventId }: EsBackLinkProps) {
  const href =
    investigationContext?.es_back_url ||
    investigationContext?.es_links?.mission_control ||
    investigationContext?.es_links?.incident_review;

  if (!href) {
    return null;
  }

  const hasEvent = Boolean(eventId || investigationContext?.event_id);
  const label = hasEvent ? "Back to Mission Control" : "Open ES Mission Control";

  return (
    <a
      className="es-back-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="Return to Splunk Enterprise Security investigation"
    >
      {label}
    </a>
  );
}
