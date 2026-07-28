/** Fallback pattern list — synced with pattern_catalog.py; API list_patterns overrides at runtime. */
export interface PatternDefinition {
  id: string;
  label: string;
  description?: string;
  offline?: boolean;
  category?: string;
  integrations?: string[];
  tier?: string;
  requires_confirm?: boolean;
  destructive_actions?: string[];
  org?: boolean;
  trusted_ir?: boolean;
  template_kind?: string;
}

export const FALLBACK_PATTERNS: PatternDefinition[] = [
  { id: "hello", label: "Hello World", category: "Getting started", offline: true, integrations: [] },
  {
    id: "failed-logins-okta",
    label: "Excessive Failed Logins (Okta)",
    category: "Identity & access",
    description: "Access — Excessive Failed Logins IDP response",
    integrations: ["okta"],
    offline: true,
  },
  {
    id: "okta-idp-response",
    label: "Okta IDP Response",
    category: "Identity & access",
    integrations: ["okta"],
    offline: true,
  },
  {
    id: "insider-threat-ad",
    label: "Insider Threat — AD Disable",
    category: "Identity & access",
    integrations: ["active_directory"],
    offline: true,
  },
  {
    id: "es-notable-response",
    label: "ES Notable Response",
    category: "Splunk ES",
    integrations: [],
    offline: true,
  },
  {
    id: "clearpass-quarantine",
    label: "Aruba ClearPass Quarantine",
    category: "Network & NAC",
    integrations: ["clearpass_cppm", "splunk_enterprise"],
    offline: true,
  },
  {
    id: "panw-block-ip",
    label: "Palo Alto Block IP",
    category: "Network & NAC",
    integrations: ["panw", "splunk_enterprise"],
    offline: true,
  },
  {
    id: "servicenow-incident",
    label: "ServiceNow P1 Incident",
    category: "ITSM & ticketing",
    integrations: ["servicenow"],
    offline: true,
  },
  {
    id: "indicator-enrichment",
    label: "Indicator Enrichment (IOCs)",
    category: "Threat enrichment",
    integrations: ["virustotalv3"],
    offline: true,
  },
  {
    id: "virustotal-enrichment",
    label: "VirusTotal File Hash",
    category: "Threat enrichment",
    integrations: ["virustotalv3"],
    offline: true,
  },
  {
    id: "phishing-enrichment",
    label: "Phishing URL Enrichment",
    category: "Threat enrichment",
    integrations: [],
    offline: true,
  },
];

export function patternsFromApiPayload(data: {
  patterns?: Array<Record<string, unknown>>;
  by_category?: Record<string, Array<Record<string, unknown>>>;
  org_template_count?: number;
  org_errors?: string[];
  org_warnings?: string[];
}): {
  patterns: PatternDefinition[];
  byCategory: Record<string, PatternDefinition[]>;
  orgTemplateCount: number;
  orgErrors: string[];
  orgWarnings: string[];
} {
  const patterns: PatternDefinition[] = (data.patterns || []).map((row) => ({
    id: String(row.id),
    label: String(row.label || row.id),
    description: row.description ? String(row.description) : undefined,
    category: row.category ? String(row.category) : undefined,
    integrations: Array.isArray(row.integrations) ? row.integrations.map(String) : [],
    offline: row.offline !== false,
    tier: row.tier ? String(row.tier) : undefined,
    requires_confirm: Boolean(row.requires_confirm),
    destructive_actions: Array.isArray(row.destructive_actions)
      ? row.destructive_actions.map(String)
      : [],
    org: Boolean(row.org),
    trusted_ir: Boolean(row.trusted_ir),
    template_kind: row.template_kind ? String(row.template_kind) : undefined,
  }));
  const byCategory: Record<string, PatternDefinition[]> = {};
  if (data.by_category) {
    for (const [cat, items] of Object.entries(data.by_category)) {
      byCategory[cat] = items.map((row) => ({
        id: String(row.id),
        label: String(row.label || row.id),
        description: row.description ? String(row.description) : undefined,
        category: cat,
        integrations: Array.isArray(row.integrations) ? row.integrations.map(String) : [],
        offline: row.offline !== false,
        tier: row.tier ? String(row.tier) : undefined,
        requires_confirm: Boolean(row.requires_confirm),
        org: Boolean(row.org),
        trusted_ir: Boolean(row.trusted_ir),
        template_kind: row.template_kind ? String(row.template_kind) : undefined,
      }));
    }
  }
  return {
    patterns,
    byCategory,
    orgTemplateCount: Number(data.org_template_count || 0),
    orgErrors: Array.isArray(data.org_errors) ? data.org_errors.map(String) : [],
    orgWarnings: Array.isArray(data.org_warnings)
      ? data.org_warnings.map(String)
      : [],
  };
}
