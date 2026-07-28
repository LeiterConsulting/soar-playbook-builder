import type { BuilderResponse } from "../types";
import { DEMO_SAMPLE_CASES, SHOWCASE_SAMPLE_IDS, demoSampleById } from "../demoSamples";
import {
  isBuildIntent,
  matchPattern,
  parseBuilderAction,
  shouldDeferToLlm,
} from "../lib/localNlBuild";
import { FALLBACK_PATTERNS } from "../patterns/catalog";

export const MOCK_SAMPLE_CASES = DEMO_SAMPLE_CASES;

const HELLO_SOURCE = `import phantom.app as phantom


def on_start(container):
    phantom.debug("Playbook started on container %s" % container["id"])


def on_finish(container):
    phantom.debug("Playbook finished")
`;

export const MOCK_PREVIEW = [
  { type: "start", label: "Start", detail: "on_start" },
  { type: "action", label: "debug", detail: "phantom.debug", app: "Splunk SOAR" },
  { type: "end", label: "Finish", detail: "on_finish" },
];

export function mockListPatterns(): BuilderResponse {
  return {
    status: "success",
    patterns: FALLBACK_PATTERNS.map((p) => ({
      id: p.id,
      label: p.label,
      description: p.description,
      category: p.category,
      integrations: p.integrations,
      tier: p.tier,
    })),
    by_category: FALLBACK_PATTERNS.reduce<Record<string, typeof FALLBACK_PATTERNS>>((acc, p) => {
      const cat = p.category || "General";
      acc[cat] = acc[cat] || [];
      acc[cat].push(p);
      return acc;
    }, {}),
  };
}

export function mockScaffold(pattern: string): BuilderResponse {
  const row = FALLBACK_PATTERNS.find((p) => p.id === pattern) || FALLBACK_PATTERNS[0];
  return {
    status: "success",
    pattern: row.id,
    pattern_label: row.label,
    source: HELLO_SOURCE,
    draft_ready: true,
    preview: MOCK_PREVIEW,
    analysis: { score: 85, valid_python: true, findings: [] },
    content: `Scaffolded **${row.label}** playbook (mock mode).`,
  };
}

const MOCK_OFFLINE_NOTE =
  "\n\n_(Mock mode — offline builder. On SOAR with MCP bridge up, custom prompts use the LLM instead of keyword templates.)_";

function withOfflineFlags(response: BuilderResponse): BuilderResponse {
  return {
    ...response,
    offline_mode: true,
    content: `${response.content || ""}${MOCK_OFFLINE_NOTE}`,
  };
}

function mockGenericStub(message: string): BuilderResponse {
  const snippet = message.replace(/"/g, "'").replace(/\s+/g, " ").slice(0, 100);
  const source = `import phantom.app as phantom

# Offline stub (mock mode). Connect MCP bridge on SOAR for a full LLM draft.


def on_start(container):
    phantom.debug("Build request: ${snippet}")
    phantom.collect2(
        container=container,
        datapath=["artifact:*.cef.sourceAddress"],
    )
    phantom.add_note(
        container=container,
        title="Playbook stub",
        content="Playbook stub — customize actions",
    )
    on_finish(container)


def on_finish(container):
    phantom.debug("Playbook finished")
`;
  return {
    status: "success",
    pattern: "nl-generated",
    pattern_label: "Generated playbook (offline)",
    source,
    draft_ready: true,
    preview: [
      { type: "start", label: "Start", detail: "on_start" },
      { type: "collect", label: "Collect artifacts", detail: "sourceAddress" },
      { type: "action", label: "add_note", app: "Splunk SOAR", detail: "Playbook stub" },
      { type: "end", label: "Finish", detail: "on_finish" },
    ],
    analysis: { score: 70, valid_python: true, findings: [] },
    offline_mode: true,
    llm_fallback: true,
    content:
      "Generated a **starter playbook** offline (mock mode).\n\n" +
      "- Your prompt needs integrations outside the catalog — keyword templates were skipped.\n" +
      "- Score 70/100" +
      MOCK_OFFLINE_NOTE,
  };
}

function patternKnown(pattern: string): boolean {
  return FALLBACK_PATTERNS.some((p) => p.id === pattern);
}

/** Same routing order as playbook_builder_connector chat handler (mock / localhost). */
export function mockChat(message: string, _pattern?: string, lane?: string): BuilderResponse {
  const trimmed = message.trim();
  if (!trimmed) {
    return { status: "error", error: "message required" };
  }

  const lower = trimmed.toLowerCase();
  if (lane === "tutor" || lower.startsWith("lesson ") || lower.startsWith("quiz") || lower.startsWith("explain")) {
    return mockTutorChat(trimmed);
  }

  if (lower === "validate current preview" || lower === "validate preview") {
    return mockScaffold("hello");
  }

  const explicit = parseBuilderAction(trimmed);
  if (explicit) {
    const key = matchPattern(`scaffold ${explicit}`) || explicit.replace(/_/g, "-");
    return withOfflineFlags(mockScaffold(patternKnown(key) ? key : "hello"));
  }

  if (!isBuildIntent(trimmed)) {
    return {
      status: "error",
      error: "Mock: not a build request — start with “Build a playbook that…” or use Templates.",
    };
  }

  if (!shouldDeferToLlm(trimmed)) {
    const matched = matchPattern(trimmed);
    if (matched && patternKnown(matched)) {
      return withOfflineFlags(mockScaffold(matched));
    }
  }

  if (/slack|#/.test(lower) && !shouldDeferToLlm(trimmed)) {
    return {
      status: "success",
      pattern: "nl-generated",
      pattern_label: "NL Draft",
      draft_ready: true,
      source: `import phantom.app as phantom

def on_start(container):
    severity = container.get("severity", "")
    if severity.lower() in ("high", "critical"):
        phantom.act(
            "send message",
            parameters={"destination": "#soc-alerts", "message": "Case alert"},
            assets=["slack_lab"],
            name="notify_soc",
        )
    on_finish(container)

def on_finish(container):
    phantom.debug("done")
`,
      preview: [
        { type: "start", label: "Start" },
        { type: "decision", label: "Severity check", detail: "high / critical" },
        { type: "action", label: "send message", app: "Slack", detail: "#soc-alerts" },
        { type: "end", label: "Finish" },
      ],
      content: "Mock NL draft with Slack action (mock mode).",
    };
  }

  return mockGenericStub(trimmed);
}

export function mockInvestigationContext(params: Record<string, string | undefined>): BuilderResponse {
  const cid = params.container_id || "9001";
  const sample =
    MOCK_SAMPLE_CASES.find((c) => String(c.id) === String(cid)) || MOCK_SAMPLE_CASES[0];
  const rule = params.rule_name || sample.rule_name || "Failed Logins";
  const event = params.event_id || sample.event_id || "mock-event-001";
  const suggested =
    sample.fixture_pattern_id ||
    (/phish|url/i.test(rule)
      ? "phishing-enrichment"
      : /insider|ueba/i.test(rule)
        ? "insider-threat-ad"
        : /hello|demo/i.test(rule)
          ? "hello"
          : "failed-logins-okta");
  return {
    status: "success",
    message: `Case ${cid} · rule ${rule} · suggested template ${suggested}`,
    suggested_pattern: suggested,
    wizard_scenario_id: suggested,
    investigation_context: {
      event_id: event,
      rule_name: rule,
      es_back_url:
        "http://localhost:8000/en-US/app/SplunkEnterpriseSecuritySuite/ess_investigation?event_id=mock-event-001",
      es_links: {
        mission_control:
          "http://localhost:8000/en-US/app/SplunkEnterpriseSecuritySuite/ess_investigation?event_id=mock-event-001",
      },
      container: {
        id: Number(cid) || cid,
        name: sample.name,
        severity: sample.severity,
      },
      cef: { user: "jdoe", sourceAddress: "10.0.0.5" },
      artifact_count: 2,
    },
    container_id: cid,
  };
}

export function mockListCases(): BuilderResponse {
  return {
    status: "success",
    cases: [
      ...MOCK_SAMPLE_CASES,
      {
        id: 42,
        name: "Live SOAR case (mock)",
        severity: "high",
        status: "open",
        label: "investigation",
        source: "soar",
        event_id: "mock-live-event",
        rule_name: "Suspicious PowerShell",
        summary: "Mock live container from SOAR REST",
      },
    ],
    sample_count: MOCK_SAMPLE_CASES.length,
    live_count: 1,
    showcase_sample_ids: SHOWCASE_SAMPLE_IDS,
    message: `${MOCK_SAMPLE_CASES.length + 1} cases available (${MOCK_SAMPLE_CASES.length} sample, 1 from SOAR).`,
  };
}

export function mockBridgeStatus(): BuilderResponse {
  const mockLlm = import.meta.env.VITE_MOCK_LLM === "true";
  return {
    status: "success",
    reachable: true,
    llm_configured: mockLlm,
    llm_mode: mockLlm ? "cloud" : "stub",
    llm_model: mockLlm ? "gpt-4o-mini" : undefined,
    llm_hint: mockLlm
      ? undefined
      : "Mock: set VITE_MOCK_LLM=true in .env.local to simulate LLM ready",
    hint: mockLlm ? "Mock mode — LLM configured" : "Mock mode — bridge up, LLM not configured",
  };
}

export function mockEnvironmentCheck(): BuilderResponse {
  const mockLlm = import.meta.env.VITE_MOCK_LLM === "true";
  return {
    status: "success",
    nl_ready: mockLlm,
    nl_mode: mockLlm ? "llm" : "bridge_stub",
    bridge_reachable: true,
    llm_configured: mockLlm,
    message: mockLlm
      ? "Natural language ready — MCP bridge and LLM configured (mock)."
      : "MCP bridge online but LLM not configured — templates/stubs only for custom NL (mock).",
    checks: [
      {
        id: "mcp_bridge",
        severity: "ok",
        title: "MCP bridge",
        detail: mockLlm
          ? "Online — LLM ready (gpt-4o-mini, cloud)"
          : "Online — bridge reachable; LLM not configured (custom NL returns stubs/templates only)",
      },
      {
        id: "llm",
        severity: mockLlm ? "ok" : "warn",
        title: "LLM / model API",
        detail: mockLlm
          ? "Configured — gpt-4o-mini"
          : "Set OPENAI_API_KEY or OPENAI_BASE_URL on MCP bridge host",
      },
      {
        id: "asset_defaults",
        severity: "info",
        title: "Asset defaults",
        detail: "Not set — integration preflight may ask for assets at import",
      },
      {
        id: "demo_data",
        severity: "ok",
        title: "Demo cases",
        detail: `${MOCK_SAMPLE_CASES.length} sample cases + runtime fixtures`,
      },
      {
        id: "ui_persona",
        severity: "info",
        title: "UI persona",
        detail: "default_ui_mode=studio — append ?mode=coach|assistant|tutor or use es_link / splunk_link",
      },
      {
        id: "capability_index",
        severity: "info",
        title: "Capability index",
        detail: "Not built — run rebuild capability index (mock)",
      },
    ],
    setup_complete: false,
    capability_index_loaded: false,
    default_ui_mode: "studio",
    fixes: [
      {
        id: "rebuild_capability_index",
        label: "Rebuild capability index",
        action: "rebuild_capability_index",
      },
      {
        id: "export_asset_config",
        label: "Export asset config",
        action: "export_asset_config",
      },
      {
        id: "run_self_test",
        label: "Run self-test",
        action: "run_self_test",
      },
      {
        id: "apply_asset_defaults",
        label: "Fix environment (apply defaults)",
        action: "apply_environment_fixes",
        auto: true,
      },
      { id: "use_template", label: "Use template instead", action: "scaffold" },
      { id: "provision_demo", label: "Create demo case on SOAR", action: "provision_demo_case" },
    ],
    suggested_asset_defaults: { okta: "okta", slack: "slack_lab", soar: "soar" },
    demo_sample_ids: MOCK_SAMPLE_CASES.map((c) => Number(c.id)),
    showcase_sample_ids: SHOWCASE_SAMPLE_IDS,
  };
}

let mockDemoContainerSeq = 9100;

export function mockApplyEnvironmentFixes(body: Record<string, unknown>): BuilderResponse {
  const confirm =
    body.confirm === true || body.confirm === 1 || body.confirm === "1" || body.confirm === "true";
  const proposed = { okta: "okta", slack: "slack_lab", soar: "soar" };
  if (!confirm) {
    return {
      status: "success",
      needs_confirm: true,
      message: 'Apply asset_defaults on this Playbook Builder asset?\n\n`{"okta":"okta","slack":"slack_lab","soar":"soar"}`',
      proposed_asset_defaults: proposed,
      proposed_additions: ["okta→okta", "slack→slack_lab", "soar→soar"],
      suggested_asset_defaults: proposed,
    };
  }
  return {
    status: "success",
    message: "Applied asset_defaults: okta→okta, slack→slack_lab, soar→soar",
    fixes_applied: ["asset_defaults: okta→okta, slack→slack_lab, soar→soar"],
    asset_defaults: '{"okta":"okta","slack":"slack_lab","soar":"soar"}',
    proposed_asset_defaults: proposed,
    environment: {
      status: "success",
      nl_ready: true,
      nl_mode: "offline_templates",
      checks: [
        {
          id: "asset_defaults",
          severity: "ok",
          title: "Asset defaults",
          detail: "okta→okta, slack→slack_lab, soar→soar",
        },
      ],
    },
  };
}

export function mockProvisionDemoCase(body: Record<string, unknown>): BuilderResponse {
  const confirm =
    body.confirm === true || body.confirm === 1 || body.confirm === "1" || body.confirm === "true";
  const sid = Number(body.sample_id);
  const sample = demoSampleById(sid);
  const pid = String(body.pattern_id || sample?.fixture_pattern_id || "hello");
  if (!confirm) {
    return {
      status: "success",
      needs_confirm: true,
      pattern_id: pid,
      message: `Create demo case for **${pid}** on SOAR (container + artifacts)?`,
    };
  }
  mockDemoContainerSeq += 1;
  return {
    status: "success",
    container_id: mockDemoContainerSeq,
    pattern_id: pid,
    artifact_count: 2,
    message: `Demo case **${mockDemoContainerSeq}** ready for **${pid}**.`,
  };
}

export function mockReadiness(): BuilderResponse {
  return {
    status: "success",
    readiness: {
      ready: true,
      ready_for_import: true,
      items: [
        { id: "code", category: "code", severity: "ok", title: "Python valid", detail: "on_start present" },
        {
          id: "integrations",
          category: "integrations",
          severity: "ok",
          title: "Integrations",
          detail: "Mock assets resolved",
        },
      ],
      auto_fix_count: 0,
    },
  };
}

export function mockTroubleshoot(): BuilderResponse {
  return {
    status: "success",
    entries: [
      {
        id: "mock_offline",
        title: "Mock mode",
        severity: "info",
        symptom: "Running without SOAR",
        cause: "VITE_USE_MOCKS or dev without handler base",
        fix_steps: ["Set VITE_SOAR_HANDLER_BASE for live SOAR", "Or deploy to SOAR sidecar URL"],
        verify: "npm run dev shows mock responses",
      },
    ],
  };
}

export function mockImport(): BuilderResponse {
  return {
    status: "success",
    playbook_id: 90001,
    playbook_name: "mock_playbook",
    playbook_display_name: "Mock Playbook",
    playbook_slug: "mock_playbook",
    content: "Imported playbook id **90001** (mock).",
    soar_links: { playbooks_search: "#" },
  };
}

export function mockRun(): BuilderResponse {
  return {
    status: "success",
    playbook_run_id: 42,
    message: "Mock playbook run started on case 9001",
  };
}

export function mockListLessons(): BuilderResponse {
  return {
    status: "success",
    count: 4,
    lessons: [
      { slug: "lessons/01-hello-playbook", title: "Your first playbook" },
      { slug: "concepts/datapaths", title: "Datapaths" },
      { slug: "lessons/05-packaging-import", title: "Packaging and import" },
      { slug: "patterns/es-notable-response", title: "ES notable response" },
    ],
  };
}

export function mockGetLesson(slug: string): BuilderResponse {
  return {
    status: "success",
    slug,
    title: slug,
    tutor_lane: "lesson",
    content: `**Mock lesson:** ${slug}\n\nClassic playbooks use \`on_start(container)\` as the entry point.`,
  };
}

export function mockCoachSuggest(params: Record<string, string | undefined>): BuilderResponse {
  const ctx = mockInvestigationContext(params);
  return {
    status: "success",
    coach_lane: "respond",
    suggested_pattern: ctx.suggested_pattern,
    pattern_label: "Excessive Failed Logins (Okta)",
    case_summary: `Case **${params.container_id || "9001"}** · rule ${params.rule_name || "Failed Logins"}`,
    content:
      "**Response coach**\n\n" +
      `Case **${params.container_id || "9001"}** · Failed Logins\n\n` +
      "**Suggested template:** Excessive Failed Logins (Okta) (`failed-logins-okta`)",
    investigation_context: ctx.investigation_context,
  };
}

export function mockTutorChat(message: string): BuilderResponse {
  const lower = message.toLowerCase();
  if (lower.startsWith("lesson ")) {
    return mockGetLesson(message.split(/\s+/)[1] || "curriculum");
  }
  if (lower.startsWith("quiz")) {
    return {
      status: "success",
      tutor_lane: "quiz",
      content:
        "**Quiz — datapaths**\n\nWhich datapath collects source IPs?\n\nb) artifact:*.cef.sourceAddress",
    };
  }
  return {
    status: "success",
    tutor_lane: "explain",
    content:
      "**Datapath:** `artifact:*.cef.sourceAddress`\n\nReads from container artifacts. CEF uses camelCase.",
  };
}
