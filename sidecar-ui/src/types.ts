export interface PreviewBlock {
  type?: string;
  label?: string;
  summary?: string;
  detail?: string;
  action?: string;
  app?: string;
  app_label?: string;
  /** Pipe-delimited human field names (collect blocks). */
  fields?: string;
  /** Pipe-delimited raw datapaths (collect blocks). */
  datapaths?: string;
  callback?: string;
  function?: string;
  branches?: string;
}

export interface StoryLane {
  lane?: string;
  title?: string;
  detail?: string;
}

export interface BuilderStep {
  id?: string;
  title: string;
  summary?: string;
  prompts?: string[];
}

export interface AnalysisResult {
  score: number;
  valid_python?: boolean;
  findings?: Array<{ level: string; message: string }>;
}

export interface TroubleshootingEntry {
  id: string;
  title: string;
  severity: string;
  symptom: string;
  cause: string;
  fix_steps: string[];
  verify: string;
}

export interface BuilderResponse {
  status?: string;
  error?: string;
  http_status?: number;
  raw_body?: string;
  content?: string;
  message?: string;
  preview?: PreviewBlock[];
  storyboard?: StoryLane[];
  source?: string;
  analysis?: AnalysisResult | null;
  pattern?: string;
  pattern_id?: string;
  pattern_label?: string;
  draft_ready?: boolean;
  llm_fallback?: boolean;
  offline_mode?: boolean;
  bridge_reachable?: boolean;
  llm_configured?: boolean;
  llm_mode?: string;
  llm_model?: string;
  llm_hint?: string;
  playbook_id?: string | number;
  playbook_name?: string;
  playbook_display_name?: string;
  playbook_slug?: string;
  playbook_search?: string;
  import_error?: string;
  import_attempts?: string[];
  import_steps?: ImportStep[];
  asset_preflight?: AssetPreflight;
  readiness?: ReadinessReport;
  fixes_applied?: string[];
  soar_links?: Record<string, string> | null;
  changed?: boolean;
  reachable?: boolean;
  hint?: string;
  steps?: BuilderStep[];
  troubleshooting?: TroubleshootingEntry;
  entries?: TroubleshootingEntry[];
  count?: number;
  patterns?: Array<{
    id: string;
    label: string;
    description?: string;
    category?: string;
    integrations?: string[];
    offline?: boolean;
    tier?: string;
    requires_confirm?: boolean;
    destructive_actions?: string[];
  }>;
  by_category?: Record<
    string,
    Array<{
      id: string;
      label: string;
      description?: string;
      integrations?: string[];
      tier?: string;
      requires_confirm?: boolean;
    }>
  >;
  suggested_pattern?: string;
  wizard_scenario_id?: string;
  investigation_context?: InvestigationContext;
  tier?: string;
  requires_destructive_confirm?: boolean;
  destructive_actions?: string[];
  playbook_run_id?: string | number;
  container_id?: string | number;
  cases?: CaseSummary[];
  sample_count?: number;
  live_count?: number;
  error_detail?: string | null;
  checks?: Array<{ id: string; severity: string; title: string; detail: string }>;
  fixes?: Array<{ id: string; label: string; action?: string; hint?: string; auto?: boolean }>;
  nl_mode?: string;
  nl_ready?: boolean;
  needs_confirm?: boolean;
  coach_lane?: string;
  tutor_lane?: string;
  case_summary?: string;
  case_intel?: { run_count?: number; recent_runs?: Array<Record<string, unknown>> };
  default_ui_mode?: string;
  lessons?: Array<{ slug: string; title: string }>;
  slug?: string;
  title?: string;
  artifact_count?: number;
  demo_sample_ids?: number[];
  showcase_sample_ids?: number[];
  blocking_count?: number;
  suggested_asset_defaults?: Record<string, string>;
  proposed_asset_defaults?: Record<string, string>;
  proposed_additions?: string[];
  environment?: BuilderResponse;
  asset_defaults?: string;
  copy_json?: string;
  field_count?: number;
  setup_complete?: boolean;
  capability_index_loaded?: boolean;
  app_count?: number;
  action_count?: number;
  harvest_status?: string;
  passed?: number;
  blocking?: number;
  check_count?: number;
}

export interface CaseSummary {
  id: number | string;
  name: string;
  severity?: string;
  status?: string;
  label?: string;
  source?: "soar" | "sample" | string;
  event_id?: string;
  rule_name?: string;
  fixture_pattern_id?: string;
  demo_tier?: "safe" | "integration" | "destructive" | string;
  showcase_recommended?: boolean;
  summary?: string;
}

export interface InvestigationContext {
  container?: {
    id?: number | string;
    name?: string;
    severity?: string;
    status?: string;
    label?: string;
  };
  cef?: Record<string, string>;
  artifact_count?: number;
  suggested_pattern?: string;
  wizard_scenario_id?: string;
  message?: string;
  event_id?: string;
  rule_name?: string;
  investigation_id?: string;
  es_back_url?: string;
  es_links?: {
    mission_control?: string;
    incident_review?: string;
    es_home?: string;
  };
}

export type PreviewTab = "blocks" | "diagram" | "story" | "code";

export type SyncStatus =
  | { kind: "idle" }
  | { kind: "pending"; message: string }
  | { kind: "ok"; message: string }
  | { kind: "error"; message: string };

export interface ImportStep {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error" | "skipped" | "warning";
  detail?: string;
}

export interface AssetCandidate {
  id?: string | number;
  name?: string;
  product_name?: string;
  product_code?: string;
}

export interface AssetRequirement {
  key: string;
  label?: string;
  status: string;
  resolved_name?: string;
  resolution?: string;
  candidates?: AssetCandidate[];
}

export interface AssetPreflight {
  ready?: boolean;
  required?: string[];
  requirements?: AssetRequirement[];
  asset_map?: Record<string, string>;
  missing?: string[];
  ambiguous?: string[];
  configured_count?: number;
}

export interface ReadinessItem {
  id: string;
  category: string;
  severity: string;
  title: string;
  detail?: string;
  auto_fixable?: boolean;
  fix_id?: string;
}

export interface ReadinessReport {
  ready?: boolean;
  ready_for_import?: boolean;
  ready_for_run?: boolean;
  items?: ReadinessItem[];
  error_count?: number;
  warning_count?: number;
  auto_fix_count?: number;
  available_fixes?: string[];
  asset_preflight?: AssetPreflight;
}

export interface ChatMessage {
  id: string;
  role: "user" | "bot";
  text: string;
}
