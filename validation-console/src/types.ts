export type CheckStatus = "ok" | "warn" | "error" | "skipped" | "manual";

export interface E2ECheck {
  id: string;
  phase: string;
  title: string;
  status: CheckStatus;
  message: string;
  automated: boolean;
  verify_url?: string | null;
  manual_verify?: string | null;
  detail?: Record<string, unknown>;
}

export interface E2EReport {
  status: CheckStatus;
  timestamp: string;
  mode: string;
  summary: Record<CheckStatus, number>;
  links: Record<string, string>;
  context: Record<string, string>;
  checks: E2ECheck[];
}

export interface ConsoleConfig {
  soarUrl: string;
  soarUser: string;
  hasPassword: boolean;
  verifySsl: string;
  assetName: string;
  mcpBridgeUrl: string;
  e2eMode: string;
  envReady: boolean;
  missingEnv: string[];
  phases: string[];
}

export interface ValidationPhase {
  id: string;
  title: string;
  subtitle: string;
  whatYouDo: string;
  whatAutomationDoes: string;
  passCriteria: string;
  linkKeys: string[];
}
