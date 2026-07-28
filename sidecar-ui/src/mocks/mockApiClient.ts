import type { ApiClientOptions } from "../api";
import type { BuilderResponse } from "../types";
import {
  mockApplyEnvironmentFixes,
  mockBridgeStatus,
  mockChat,
  mockCoachSuggest,
  mockEnvironmentCheck,
  mockGetLesson,
  mockImport,
  mockInvestigationContext,
  mockListCases,
  mockListLessons,
  mockListPatterns,
  mockProvisionDemoCase,
  mockReadiness,
  mockRun,
  mockScaffold,
  mockTroubleshoot,
} from "./fixtures";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** In-memory mock API for local dev without SOAR. */
export function createMockApiClient(opts: ApiClientOptions) {
  async function apiGet(qs: Record<string, string | undefined>): Promise<BuilderResponse> {
    await delay(120);
    const action = qs.action || "";
    if (action === "list_patterns") return mockListPatterns();
    if (action === "bridge_status") return mockBridgeStatus();
    if (action === "environment_check") return mockEnvironmentCheck();
    if (action === "scaffold") return mockScaffold(qs.pattern || opts.getPattern());
    if (action === "validate") return mockScaffold(qs.pattern || opts.getPattern());
    if (action === "list_cases") return mockListCases();
    if (action === "investigation_context") {
      const ctx = opts.getUrlContext();
      return mockInvestigationContext({
        event_id: ctx.eventId,
        rule_name: ctx.ruleName,
        container_id: ctx.containerId,
        investigation_id: ctx.investigationId,
      });
    }
    if (action === "coach_suggest") {
      const ctx = opts.getUrlContext();
      return mockCoachSuggest({
        rule_name: ctx.ruleName,
        container_id: ctx.containerId,
      });
    }
    if (action === "list_lessons") return mockListLessons();
    if (action === "get_lesson") return mockGetLesson(qs.slug || qs.lesson || "");
    if (action === "troubleshoot") return mockTroubleshoot();
    if (qs.message) return mockChat(qs.message, qs.pattern, qs.lane);
    return { status: "error", error: `Mock: unknown GET action ${action || "none"}` };
  }

  async function apiPost(body: Record<string, unknown>): Promise<BuilderResponse> {
    await delay(180);
    const action = String(body.action || "");
    if (action === "chat") return mockChat(String(body.message || ""), String(body.pattern || ""), String(body.lane || ""));
    if (action === "readiness_check") return mockReadiness();
    if (action === "import_draft") return mockImport();
    if (action === "run_playbook") return mockRun();
    if (action === "provision_demo_case") return mockProvisionDemoCase(body);
    if (action === "apply_environment_fixes") return mockApplyEnvironmentFixes(body);
    if (action === "rebuild_capability_index") {
      return {
        status: "success",
        message: "Capability index rebuilt — 6 apps, 11 actions (mock)",
        app_count: 6,
        action_count: 11,
        harvest_status: "partial",
      };
    }
    if (action === "export_asset_config") {
      return {
        status: "success",
        message: "Asset configuration exported (mock)",
        field_count: 2,
        copy_json: '{"export_version":"1.0","configuration":{"ai_instructions":"mock"}}',
      };
    }
    if (action === "run_self_test") {
      return {
        status: "success",
        message: "Self-test passed (mock)",
        setup_complete: true,
        checks: [
          { id: "capability_index", title: "Capability index", severity: "ok", detail: "6 apps" },
          { id: "hello_template", title: "Hello template", severity: "ok", detail: "Python validates" },
        ],
      };
    }
    if (action === "preflight_import") {
      return {
        status: "success",
        asset_preflight: { ready: true, requirements: [], asset_map: {} },
      };
    }
    return { status: "error", error: `Mock: unknown POST action ${action}` };
  }

  return {
    apiGet,
    apiPost,
    apiChat: (message: string, pattern?: string) => apiPost({ action: "chat", message, pattern }),
    apiTroubleshoot: () => apiGet({ action: "troubleshoot" }),
  };
}

export type ApiClient = ReturnType<typeof createMockApiClient>;
