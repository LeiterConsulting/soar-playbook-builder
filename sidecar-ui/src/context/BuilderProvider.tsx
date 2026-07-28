import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  createApiClient,
  readUrlContext,
  resolveHandlerBase,
  responseHasPayload,
  shouldUseMocks,
} from "../api";
import { listPatterns } from "../patterns/registry";
import { patternsFromApiPayload } from "../patterns/catalog";
import type { WizardScenario } from "../patterns/scenarios";
import type {
  AssetPreflight,
  BuilderResponse,
  CaseSummary,
  ChatMessage,
  ImportStep,
  InvestigationContext,
  PreviewBlock,
  ReadinessReport,
  SyncStatus,
  TroubleshootingEntry,
} from "../types";
import {
  advanceClientImportSteps,
  buildAssetMap,
  CLIENT_IMPORT_PHASES,
  destructiveConfirmMessage,
  isDestructivePattern,
  nextMsgId,
  playbookSearchSlug,
} from "../lib/playbookUtils";
import type { WorkflowStep } from "../components/WorkflowStrip";
import type { PatternDefinition } from "../patterns/catalog";
import {
  readCoachTab,
  readPersonaMode,
  writeCoachTab,
  type CoachTab,
  type PersonaMode,
} from "../personas";

/** Survives React Strict Mode remount — boot messages must not repeat. */
let hasBootstrapped = false;

export interface BuilderContextValue {
  urlCtx: ReturnType<typeof readUrlContext>;
  handlerBase: string;
  instructions: string;
  linkedPlaybookId: string;
  linkedPlaybookName: string;
  linkedPlaybookSlug: string;
  linkedPlaybookSearch: string;
  draftLabel: string;
  currentPattern: string;
  setCurrentPattern: (p: string) => void;
  currentSource: string;
  draftReady: boolean;
  busy: boolean;
  activePreviewTab: "blocks" | "code";
  setActivePreviewTab: (t: "blocks" | "code") => void;
  preview: PreviewBlock[];
  scoreLabel: string;
  syncStatus: SyncStatus;
  messages: ChatMessage[];
  input: string;
  setInput: (v: string) => void;
  bridgeOk: boolean | null;
  llmConfigured: boolean | null;
  importSteps: ImportStep[];
  importAttempts: string[];
  showImportLog: boolean;
  soarLinks: Record<string, string> | null;
  assetPreflight: AssetPreflight | null;
  assetSelections: Record<string, string>;
  setAssetSelections: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  showAssetPanel: boolean;
  troubleshooting: TroubleshootingEntry | null;
  setTroubleshooting: (e: TroubleshootingEntry | null) => void;
  wizardScenarioId: string | null;
  setWizardScenarioId: (id: string | null) => void;
  wizardCollapsed: boolean;
  setWizardCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  showHelp: boolean;
  setShowHelp: React.Dispatch<React.SetStateAction<boolean>>;
  helpQuery: string;
  setHelpQuery: (q: string) => void;
  helpEntries: TroubleshootingEntry[];
  helpLoading: boolean;
  patterns: PatternDefinition[];
  orgTemplateCount: number;
  patternsByCategory: Record<string, PatternDefinition[]>;
  investigationContext: InvestigationContext | null;
  readiness: ReadinessReport | null;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  workflowStep: WorkflowStep;
  ctxLabel: string;
  bridgeLabel: string;
  bridgeTitle: string;
  bridgeTone: "ok" | "warn" | "muted";
  canRunOnContainer: boolean;
  runDisabledReason: string | undefined;
  canRunReadiness: boolean;
  readinessDisabledReason: string | undefined;
  hasImportedPlaybook: boolean;
  openHref: string;
  soarHint: string;
  addMsg: (text: string, role: "user" | "bot") => void;
  sendMessage: (text?: string, opts?: { lane?: string }) => Promise<void>;
  handleImport: () => Promise<void>;
  handleRunOnContainer: () => Promise<void>;
  handleAssetConfirm: () => Promise<void>;
  handleScaffold: () => Promise<void>;
  handleValidate: () => Promise<void>;
  handleReadinessCheck: () => Promise<void>;
  handleApplyReadinessFixes: () => Promise<void>;
  handleWizardStart: (scenario: WizardScenario) => Promise<void>;
  fetchHelp: (query: string) => Promise<void>;
  linkCase: (caseRow: CaseSummary) => void;
  provisionDemoCase: (caseRow: CaseSummary) => Promise<void>;
  provisioningCaseId: string;
  apiGet: (qs: Record<string, string | undefined>) => Promise<BuilderResponse>;
  checkBridgeStatus: () => Promise<void>;
  handleFixEnvironment: () => Promise<void>;
  handleSetupAction: (action: string) => Promise<void>;
  fixingEnvironment: boolean;
  envRefreshToken: number;
  usingMocks: boolean;
  personaMode: PersonaMode;
  coachTab: CoachTab;
  setCoachTab: (tab: CoachTab) => void;
  coachSuggest: BuilderResponse | null;
  coachLoading: boolean;
  refreshCoachSuggest: () => Promise<void>;
}

const BuilderContext = createContext<BuilderContextValue | null>(null);

export function useBuilder(): BuilderContextValue {
  const ctx = useContext(BuilderContext);
  if (!ctx) throw new Error("useBuilder must be used within BuilderProvider");
  return ctx;
}

interface BuilderProviderProps {
  aiInstructions: string;
  defaultUiMode: string;
  children: ReactNode;
}

export function BuilderProvider({ aiInstructions, defaultUiMode, children }: BuilderProviderProps) {
  const [urlCtx, setUrlCtx] = useState(() => readUrlContext());
  const personaMode = useMemo(() => readPersonaMode(defaultUiMode), [defaultUiMode]);
  const [coachTab, setCoachTabState] = useState<CoachTab>(() => readCoachTab(readPersonaMode(defaultUiMode)));
  const [coachSuggest, setCoachSuggest] = useState<BuilderResponse | null>(null);
  const [coachLoading, setCoachLoading] = useState(false);
  const handlerBase = useMemo(() => resolveHandlerBase(), []);
  const usingMocks = shouldUseMocks();

  const [instructions] = useState(aiInstructions);
  const [linkedPlaybookId, setLinkedPlaybookId] = useState(
    () => readUrlContext().contextPlaybookId || "",
  );
  const [linkedPlaybookName, setLinkedPlaybookName] = useState("");
  const [linkedPlaybookSlug, setLinkedPlaybookSlug] = useState("");
  const [linkedPlaybookSearch, setLinkedPlaybookSearch] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [currentPattern, setCurrentPattern] = useState("hello");
  const [currentSource, setCurrentSource] = useState("");
  const [draftReady, setDraftReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activePreviewTab, setActivePreviewTab] = useState<"blocks" | "code">("blocks");
  const [preview, setPreview] = useState<PreviewBlock[]>([]);
  const [scoreLabel, setScoreLabel] = useState("");
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({ kind: "idle" });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [bridgeOk, setBridgeOk] = useState<boolean | null>(null);
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [importSteps, setImportSteps] = useState<ImportStep[]>([]);
  const [importAttempts, setImportAttempts] = useState<string[]>([]);
  const [showImportLog, setShowImportLog] = useState(false);
  const [soarLinks, setSoarLinks] = useState<Record<string, string> | null>(null);
  const [assetPreflight, setAssetPreflight] = useState<AssetPreflight | null>(null);
  const [assetSelections, setAssetSelections] = useState<Record<string, string>>({});
  const [showAssetPanel, setShowAssetPanel] = useState(false);
  const [troubleshooting, setTroubleshooting] = useState<TroubleshootingEntry | null>(null);
  const [wizardScenarioId, setWizardScenarioId] = useState<string | null>("failed-logins-okta");
  const [wizardCollapsed, setWizardCollapsed] = useState(true);
  const [showHelp, setShowHelp] = useState(false);
  const [helpQuery, setHelpQuery] = useState("");
  const [helpEntries, setHelpEntries] = useState<TroubleshootingEntry[]>([]);
  const [helpLoading, setHelpLoading] = useState(false);
  const [patternCatalog, setPatternCatalog] = useState(listPatterns());
  const [orgTemplateCount, setOrgTemplateCount] = useState(0);
  const [patternsByCategory, setPatternsByCategory] = useState<
    Record<string, ReturnType<typeof listPatterns>>
  >({});
  const [investigationContext, setInvestigationContext] = useState<InvestigationContext | null>(
    null,
  );
  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [provisioningCaseId, setProvisioningCaseId] = useState("");
  const [fixingEnvironment, setFixingEnvironment] = useState(false);
  const [envRefreshToken, setEnvRefreshToken] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const importTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const linkedRef = useRef(linkedPlaybookId);
  const patternRef = useRef(currentPattern);
  const urlCtxRef = useRef(urlCtx);
  linkedRef.current = linkedPlaybookId;
  patternRef.current = currentPattern;
  urlCtxRef.current = urlCtx;

  const api = useMemo(
    () =>
      createApiClient({
        handlerBase,
        getPattern: () => patternRef.current,
        getLinkedPlaybookId: () => linkedRef.current,
        getContextPlaybookId: () => urlCtxRef.current.contextPlaybookId,
        getUrlContext: () => urlCtxRef.current,
      }),
    [handlerBase],
  );

  const patterns = patternCatalog;

  const loadPatternCatalog = useCallback(async () => {
    try {
      const data = await api.apiGet({ action: "list_patterns" });
      if (data.patterns?.length) {
        const parsed = patternsFromApiPayload(data);
        setPatternCatalog(parsed.patterns);
        setPatternsByCategory(parsed.byCategory);
        setOrgTemplateCount(parsed.orgTemplateCount);
        return { orgErrors: parsed.orgErrors };
      }
    } catch {
      /* use fallback catalog */
    }
    return { orgErrors: [] as string[] };
  }, [api]);

  const setCoachTab = useCallback(
    (tab: CoachTab) => {
      setCoachTabState(tab);
      writeCoachTab(tab, personaMode);
      setUrlCtx((prev) => ({ ...prev, tab }));
    },
    [personaMode],
  );

  const addMsg = useCallback((text: string, role: "user" | "bot") => {
    setMessages((prev) => [...prev, { id: nextMsgId(), role, text }]);
  }, []);

  const applyInvestigationResponse = useCallback((ctxData: BuilderResponse) => {
    if (ctxData.suggested_pattern) {
      setCurrentPattern(String(ctxData.suggested_pattern));
      setWizardScenarioId(String(ctxData.wizard_scenario_id || ctxData.suggested_pattern));
    }
    setInvestigationContext({
      ...(ctxData.investigation_context || {}),
      ...(ctxData as InvestigationContext),
    });
  }, []);

  const refreshCoachSuggest = useCallback(async () => {
    if (personaMode !== "coach" && personaMode !== "tutor" && personaMode !== "assistant") {
      return;
    }
    setCoachLoading(true);
    try {
      const data = await api.apiGet({ action: "coach_suggest" });
      setCoachSuggest(data);
      if (data.investigation_context || data.suggested_pattern) {
        applyInvestigationResponse(data);
      }
    } catch {
      /* coach suggest is best-effort */
    } finally {
      setCoachLoading(false);
    }
  }, [api, applyInvestigationResponse, personaMode]);

  const refreshInvestigationContext = useCallback(async () => {
    if (
      !usingMocks &&
      !urlCtxRef.current.containerId &&
      !urlCtxRef.current.ruleName &&
      !urlCtxRef.current.eventId &&
      !urlCtxRef.current.investigationId
    ) {
      return;
    }
    try {
      const ctxData = await api.apiGet({ action: "investigation_context" });
      applyInvestigationResponse(ctxData);
    } catch {
      /* investigation context is best-effort */
    }
  }, [api, applyInvestigationResponse, usingMocks]);

  const linkCase = useCallback((caseRow: CaseSummary) => {
    const next = {
      ...urlCtxRef.current,
      containerId: String(caseRow.id),
      eventId: caseRow.event_id || "",
      ruleName: caseRow.rule_name || "",
    };
    setUrlCtx(next);
    urlCtxRef.current = next;

    const u = new URL(window.location.href);
    u.searchParams.set("container_id", String(caseRow.id));
    if (caseRow.event_id) u.searchParams.set("event_id", caseRow.event_id);
    else u.searchParams.delete("event_id");
    if (caseRow.rule_name) u.searchParams.set("rule_name", caseRow.rule_name);
    else u.searchParams.delete("rule_name");
    window.history.replaceState({}, "", u.toString());
  }, []);

  const provisionDemoCase = useCallback(
    async (caseRow: CaseSummary) => {
      const sid = String(caseRow.id);
      setProvisioningCaseId(sid);
      setBusy(true);
      try {
        let data = await api.apiPost({
          action: "provision_demo_case",
          sample_id: caseRow.id,
          pattern_id: caseRow.fixture_pattern_id,
        });
        if (data.needs_confirm) {
          data = await api.apiPost({
            action: "provision_demo_case",
            sample_id: caseRow.id,
            pattern_id: caseRow.fixture_pattern_id,
            confirm: true,
          });
        }
        if (data.status === "error") {
          addMsg(data.error || "Could not create demo case on SOAR.", "bot");
          if (data.troubleshooting) setTroubleshooting(data.troubleshooting);
          return;
        }
        const cid = String(data.container_id ?? "");
        if (!cid) {
          addMsg("Demo case created but container id was missing.", "bot");
          return;
        }
        if (data.pattern_id) setCurrentPattern(String(data.pattern_id));
        linkCase({
          ...caseRow,
          id: cid,
          source: "soar",
          name: caseRow.name.replace("(sample)", `(demo ${cid})`),
        });
        addMsg(
          (data.message || `Demo case ${cid} ready.`).replace(/\*\*/g, ""),
          "bot",
        );
        void refreshInvestigationContext();
      } catch (e) {
        addMsg(`Demo provision error: ${e}`, "bot");
      } finally {
        setProvisioningCaseId("");
        setBusy(false);
      }
    },
    [addMsg, api, linkCase, refreshInvestigationContext],
  );

  const setLinkedPlaybook = useCallback((id: string, name?: string, search?: string) => {
    setLinkedPlaybookId(id);
    if (name) setLinkedPlaybookName(name);
    if (search) setLinkedPlaybookSearch(search);
    const u = new URL(window.location.href);
    u.searchParams.set("playbook_id", id);
    window.history.replaceState({}, "", u.toString());
    const label = search && name && search !== name ? `${name} (${search})` : (name || search || "playbook");
    setSyncStatus({
      kind: "ok",
      message: `✓ Synced: ${label} (id ${id})`,
    });
  }, []);

  const renderPreview = useCallback(
    (data: BuilderResponse) => {
      if (data.preview) setPreview(data.preview);
      if (data.source && data.source.includes("def on_start")) {
        setCurrentSource(data.source);
        setDraftReady(true);
      } else if (data.draft_ready) {
        setDraftReady(true);
      }
      if (data.pattern_label) setDraftLabel(data.pattern_label);
      if (data.analysis) {
        setScoreLabel(`Score ${data.analysis.score}/100`);
      }
      if (data.playbook_id) {
        const name =
          data.playbook_display_name ||
          data.playbook_name ||
          data.pattern_label ||
          draftLabel ||
          linkedPlaybookName;
        if (data.playbook_slug) {
          setLinkedPlaybookSlug(data.playbook_slug);
        } else {
          setLinkedPlaybookSlug(playbookSearchSlug(name, data.pattern || currentPattern));
        }
        if (data.playbook_search) {
          setLinkedPlaybookSearch(data.playbook_search);
        } else if (data.playbook_slug) {
          setLinkedPlaybookSearch(data.playbook_slug);
        }
        setLinkedPlaybook(
          String(data.playbook_id),
          data.playbook_display_name || name,
          data.playbook_search || data.playbook_slug,
        );
      }
      if (data.soar_links) {
        setSoarLinks(data.soar_links);
      }
      if (data.import_error) {
        setSyncStatus({ kind: "error", message: `Sync failed: ${data.import_error}` });
        addMsg(`SOAR sync failed:\n${data.import_error}`, "bot");
      }
      if (data.import_steps?.length) {
        setImportSteps(data.import_steps);
        setShowImportLog(true);
      }
      if (data.import_attempts?.length) {
        setImportAttempts(data.import_attempts);
      }
      if (data.asset_preflight) {
        setAssetPreflight(data.asset_preflight);
        setShowAssetPanel(!data.asset_preflight.ready);
      }
      if (data.readiness) {
        setReadiness(data.readiness);
      }
      if (data.fixes_applied?.length) {
        addMsg(`Auto-fix applied:\n${data.fixes_applied.join("\n")}`, "bot");
      }
    },
    [addMsg, draftLabel, linkedPlaybookName, setLinkedPlaybook],
  );

  const applyResponse = useCallback(
    (data: BuilderResponse | undefined) => {
      if (!data) return;
      if (data.troubleshooting) {
        setTroubleshooting(data.troubleshooting);
      }
      if (data.status === "error" && data.error) {
        setSyncStatus({ kind: "error", message: data.error });
        if (/unknown post action:\s*readiness_check/i.test(data.error)) {
          addMsg(
            "Readiness check failed because this SOAR app is too old — the handler does not route " +
              "`readiness_check` on POST. Reinstall **SOAR Playbook Builder v2.18.0+** " +
              "(latest: dist/soar_playbook_builder.tgz), then hard-refresh the sidecar.",
            "bot",
          );
        } else {
          addMsg(data.error, "bot");
        }
        if (data.import_attempts?.length) {
          addMsg(`Import attempts:\n${data.import_attempts.join("\n")}`, "bot");
        }
        if (data.import_steps?.length) {
          setImportSteps(data.import_steps);
          setShowImportLog(true);
        }
        return;
      }
      if (data.status === "needs_assets") {
        setSyncStatus({
          kind: "error",
          message: "Configure integrations before import (see panel below).",
        });
        if (data.content) addMsg(data.content, "bot");
        renderPreview(data);
        return;
      }
      if (data.status === "needs_attention") {
        if (data.content) addMsg(data.content, "bot");
        renderPreview(data);
        return;
      }
      if (data.preview || data.source) renderPreview(data);
      if (data.pattern) setCurrentPattern(data.pattern);
      if (data.llm_fallback) {
        setSyncStatus({
          kind: "error",
          message: "LLM unavailable — placeholder stub only (not your full playbook)",
        });
      }
      if (data.offline_mode) {
        setSyncStatus({
          kind: "error",
          message: "MCP offline — used keyword template match. Fix bridge for full NL.",
        });
        if (data.suggested_pattern) setCurrentPattern(data.suggested_pattern);
      }
      if (data.content) addMsg(data.content, "bot");
      else if (!data.preview && !data.source && data.status !== "error") {
        addMsg(
          "Empty response from SOAR — reinstall soar_playbook_builder.tgz (v2.6.5+), " +
            "or pick **ServiceNow P1 Incident** from the dropdown and click **Generate template**.",
          "bot",
        );
      }
    },
    [addMsg, renderPreview],
  );

  const sendMessage = useCallback(
    async (text?: string, opts?: { lane?: string }) => {
      const msg = (text ?? input).trim();
      if (!msg || busy) return;
      addMsg(msg, "user");
      setInput("");
      setBusy(true);
      const lane =
        opts?.lane ?? (coachTab === "explain" ? "tutor" : undefined);
      try {
        let data = await api.apiChat(msg, currentPattern, lane);
        if (!responseHasPayload(data)) {
          data = await api.apiGet({ message: msg, ...(lane ? { lane } : {}) });
        }
        if (!responseHasPayload(data) && /servicenow|service now|p1 incident/i.test(msg)) {
          data = await api.apiGet({ action: "scaffold", pattern: "servicenow-incident" });
        }
        applyResponse(data);
      } catch (e) {
        const msg = String(e);
        if (msg.includes("Failed to fetch") && !usingMocks) {
          addMsg(
            "Dev mode: no SOAR backend configured.\n\n" +
              "Copy .env.example → .env.local and set VITE_SOAR_HANDLER_BASE " +
              "to your handler path (from print_sidecar_url.sh), then restart npm run dev.\n\n" +
              "Or test the built app on SOAR: install soar_playbook_builder.tgz " +
              "and open the sidecar URL there.",
            "bot",
          );
        } else {
          addMsg(`Error: ${e}`, "bot");
        }
      } finally {
        setBusy(false);
      }
    },
    [addMsg, api, applyResponse, busy, coachTab, currentPattern, input, usingMocks],
  );

  const stopImportTimer = useCallback(() => {
    if (importTimerRef.current) {
      clearInterval(importTimerRef.current);
      importTimerRef.current = null;
    }
  }, []);

  const startImportProgress = useCallback(() => {
    stopImportTimer();
    setImportAttempts([]);
    setShowImportLog(true);
    let phase = 0;
    setImportSteps(advanceClientImportSteps(CLIENT_IMPORT_PHASES, phase));
    importTimerRef.current = setInterval(() => {
      phase = Math.min(phase + 1, CLIENT_IMPORT_PHASES.length - 1);
      setImportSteps(advanceClientImportSteps(CLIENT_IMPORT_PHASES, phase));
    }, 8000);
  }, [stopImportTimer]);

  const runAssetPreflight = useCallback(async () => {
    if (!currentSource) return;
    try {
      const data = await api.apiPost({
        action: "preflight_import",
        source: currentSource,
        pattern: currentPattern,
        asset_map: buildAssetMap(assetPreflight, assetSelections),
      });
      if (data.asset_preflight) {
        setAssetPreflight(data.asset_preflight);
        setShowAssetPanel(!data.asset_preflight.ready);
      }
    } catch {
      /* preflight is best-effort */
    }
  }, [api, assetPreflight, assetSelections, currentPattern, currentSource]);

  useEffect(() => {
    if (draftReady && currentSource) {
      void runAssetPreflight();
    }
  }, [draftReady, currentSource, currentPattern, runAssetPreflight]);

  const executeImport = useCallback(
    async (assetMap: Record<string, string>, destructiveConfirm = false) => {
      setBusy(true);
      setSyncStatus({ kind: "pending", message: "Importing to SOAR…" });
      startImportProgress();
      let finished = false;
      try {
        const body: Record<string, unknown> = {
          action: "import_draft",
          confirm: true,
          source: currentSource,
          name: draftLabel || linkedPlaybookName || "NL Draft Playbook",
          pattern: currentPattern,
          asset_map: assetMap,
        };
        if (destructiveConfirm) {
          body.destructive_confirm = true;
        }
        const data = await api.apiPost(body, 120000);
        stopImportTimer();
        applyResponse(data);
        finished = data?.status === "success";
        if (data?.status === "needs_assets") {
          setShowAssetPanel(true);
        } else if (data?.status === "error") {
          setSyncStatus({ kind: "error", message: data.error || "Import failed" });
        } else if (data?.status === "success") {
          setShowAssetPanel(false);
          setSyncStatus({ kind: "ok", message: "Imported to SOAR" });
        }
      } catch (e) {
        stopImportTimer();
        setSyncStatus({ kind: "error", message: `Import failed: ${e}` });
        addMsg(`Import failed: ${e}`, "bot");
        setImportSteps((prev) =>
          prev.map((step) =>
            step.status === "running" ? { ...step, status: "error", detail: String(e) } : step,
          ),
        );
      } finally {
        stopImportTimer();
        setBusy(false);
        if (!finished) {
          setSyncStatus((prev) =>
            prev.kind === "pending"
              ? {
                  kind: "error",
                  message:
                    "Import did not complete — check integrations or retry Import.",
                }
              : prev,
          );
        }
      }
    },
    [
      addMsg,
      api,
      applyResponse,
      currentPattern,
      currentSource,
      draftLabel,
      linkedPlaybookName,
      startImportProgress,
      stopImportTimer,
    ],
  );

  const handleImport = useCallback(async () => {
    if (!draftReady || !currentSource || busy) {
      addMsg("Build a playbook first, then Import.", "bot");
      return;
    }
    const assetMap = buildAssetMap(assetPreflight, assetSelections);
    if (assetPreflight && !assetPreflight.ready) {
      const stillBlocked = (assetPreflight.requirements || []).some(
        (r) =>
          r.status === "missing" ||
          (r.status === "ambiguous" && !assetMap[r.key]),
      );
      if (stillBlocked) {
        setShowAssetPanel(true);
        addMsg(
          "Configure or map integrations below before importing — this prevents Missing Configurations in SOAR.",
          "bot",
        );
        return;
      }
    }
    const destructive = isDestructivePattern(patterns, currentPattern);
    if (destructive && !window.confirm(destructiveConfirmMessage(patterns, currentPattern))) {
      addMsg("Import cancelled — destructive template requires explicit confirmation.", "bot");
      return;
    }
    await executeImport(assetMap, destructive);
  }, [
    addMsg,
    assetPreflight,
    assetSelections,
    busy,
    currentPattern,
    currentSource,
    draftReady,
    executeImport,
    patterns,
  ]);

  const handleRunOnContainer = useCallback(async () => {
    const caseId = urlCtx.containerId || (usingMocks ? "9001" : "");
    const playbookId = linkedPlaybookId || urlCtx.contextPlaybookId;
    if (!playbookId || !caseId || busy) {
      addMsg("Import a playbook and link a SOAR case first (see Run tab → Help).", "bot");
      return;
    }
    const destructive = isDestructivePattern(patterns, currentPattern);
    if (destructive && !window.confirm(destructiveConfirmMessage(patterns, currentPattern))) {
      addMsg("Run cancelled — destructive template requires explicit confirmation.", "bot");
      return;
    }
    setBusy(true);
    setSyncStatus({ kind: "pending", message: "Starting playbook on this case…" });
    try {
      const data = await api.apiPost({
        action: "run_playbook",
        confirm: true,
        destructive_confirm: destructive,
        playbook_id: playbookId,
        container_id: caseId,
        pattern: currentPattern,
      });
      applyResponse(data);
      if (data.status === "success") {
        addMsg(data.message || `Run started (id ${data.playbook_run_id})`, "bot");
        setSyncStatus({ kind: "ok", message: data.message || "Playbook run started" });
      } else {
        setSyncStatus({ kind: "error", message: data.error || "Run failed" });
      }
    } catch (e) {
      setSyncStatus({ kind: "error", message: `Run failed: ${e}` });
      addMsg(`Run failed: ${e}`, "bot");
    } finally {
      setBusy(false);
    }
  }, [
    addMsg,
    api,
    applyResponse,
    busy,
    currentPattern,
    linkedPlaybookId,
    patterns,
    urlCtx.containerId,
    urlCtx.contextPlaybookId,
    usingMocks,
  ]);

  const handleAssetConfirm = useCallback(async () => {
    const assetMap = buildAssetMap(assetPreflight, assetSelections);
    const destructive = isDestructivePattern(patterns, currentPattern);
    if (destructive && !window.confirm(destructiveConfirmMessage(patterns, currentPattern))) {
      return;
    }
    await executeImport(assetMap, destructive);
  }, [assetPreflight, assetSelections, currentPattern, executeImport, patterns]);

  const handleScaffold = useCallback(async () => {
    try {
      applyResponse(
        await api.apiGet({ action: "scaffold", pattern: currentPattern }),
      );
    } catch (e) {
      addMsg(`Generate error: ${e}`, "bot");
    }
  }, [addMsg, api, applyResponse, currentPattern]);

  const handleValidate = useCallback(async () => {
    try {
      applyResponse(
        await api.apiGet({ action: "validate", pattern: currentPattern }),
      );
    } catch (e) {
      addMsg(`Validate error: ${e}`, "bot");
    }
  }, [addMsg, api, applyResponse, currentPattern]);

  const handleReadinessCheck = useCallback(async () => {
    if (!currentSource && !draftReady) {
      addMsg("Build or load a playbook first, then run readiness check.", "bot");
      return;
    }
    try {
      applyResponse(
        await api.apiPost({
          action: "readiness_check",
          source: currentSource,
          pattern: currentPattern,
          playbook_id: linkedPlaybookId || undefined,
          asset_map: buildAssetMap(assetPreflight, assetSelections),
        }),
      );
    } catch (e) {
      addMsg(`Readiness check error: ${e}`, "bot");
    }
  }, [
    addMsg,
    api,
    applyResponse,
    assetPreflight,
    assetSelections,
    currentPattern,
    currentSource,
    draftReady,
    linkedPlaybookId,
  ]);

  const handleApplyReadinessFixes = useCallback(async () => {
    try {
      applyResponse(
        await api.apiPost({
          action: "readiness_check",
          source: currentSource,
          pattern: currentPattern,
          apply_fixes: true,
          asset_map: buildAssetMap(assetPreflight, assetSelections),
        }),
      );
    } catch (e) {
      addMsg(`Apply fixes error: ${e}`, "bot");
    }
  }, [addMsg, api, applyResponse, assetPreflight, assetSelections, currentPattern, currentSource]);

  const handleWizardStart = useCallback(
    async (scenario: WizardScenario) => {
      setWizardScenarioId(scenario.id);
      setCurrentPattern(scenario.pattern);
      setTroubleshooting(null);
      addMsg(`Starting guided scenario: ${scenario.label}`, "bot");
      try {
        applyResponse(
          await api.apiGet({ action: "scaffold", pattern: scenario.pattern }),
        );
      } catch (e) {
        addMsg(`Scenario error: ${e}`, "bot");
      }
    },
    [addMsg, api, applyResponse],
  );

  const fetchHelp = useCallback(
    async (query: string) => {
      setHelpLoading(true);
      try {
        const data = await api.apiTroubleshoot(query);
        if (data.entries) setHelpEntries(data.entries);
      } catch {
        setHelpEntries([]);
      } finally {
        setHelpLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    if (!showHelp) return;
    const timer = setTimeout(() => void fetchHelp(helpQuery), 300);
    return () => clearTimeout(timer);
  }, [helpQuery, showHelp, fetchHelp]);

  const checkBridgeStatus = useCallback(async () => {
    try {
      const data = await api.apiGet({ action: "bridge_status" });
      setBridgeOk(Boolean(data.reachable));
      setLlmConfigured(data.reachable ? Boolean(data.llm_configured) : false);
    } catch {
      setBridgeOk(null);
      setLlmConfigured(null);
    }
  }, [api]);

  const handleFixEnvironment = useCallback(async () => {
    setFixingEnvironment(true);
    try {
      let data = await api.apiPost({ action: "apply_environment_fixes" });
      if (data.needs_confirm) {
        data = await api.apiPost({ action: "apply_environment_fixes", confirm: true });
      }
      applyResponse(data);
      if (data.fixes_applied?.length) {
        addMsg(`Environment fix:\n${data.fixes_applied.join("\n")}`, "bot");
      }
      setEnvRefreshToken((t) => t + 1);
    } catch (e) {
      addMsg(`Fix environment error: ${e}`, "bot");
    } finally {
      setFixingEnvironment(false);
    }
  }, [addMsg, api, applyResponse]);

  const handleSetupAction = useCallback(
    async (action: string) => {
      setFixingEnvironment(true);
      try {
        let data = await api.apiPost({ action });
        if (action === "export_asset_config" && data.copy_json) {
          try {
            await navigator.clipboard.writeText(String(data.copy_json));
            addMsg("Asset configuration copied to clipboard — save before migrating SOAR.", "bot");
          } catch {
            addMsg(`Export ready (${data.field_count ?? 0} fields). Copy from action result data.`, "bot");
          }
        } else if (action === "run_self_test" && data.checks) {
          const lines = data.checks
            .map((c) => {
              const ok = c.severity === "ok" || (c as { status?: string }).status === "ok";
              return `${ok ? "✓" : "○"} ${c.title}: ${c.detail}`;
            })
            .join("\n");
          addMsg(`Self-test:\n${lines}`, "bot");
        } else if (data.message) {
          addMsg(String(data.message), "bot");
        }
        if (data.needs_confirm) {
          data = await api.apiPost({ action, confirm: true });
          if (data.message) addMsg(String(data.message), "bot");
        }
        applyResponse(data);
        setEnvRefreshToken((t) => t + 1);
      } catch (e) {
        addMsg(`Setup action failed (${action}): ${e}`, "bot");
      } finally {
        setFixingEnvironment(false);
      }
    },
    [addMsg, api, applyResponse],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => stopImportTimer();
  }, [stopImportTimer]);

  useEffect(() => {
    if (hasBootstrapped) return;
    hasBootstrapped = true;
    void loadPatternCatalog();
    void checkBridgeStatus();
    const pid = readUrlContext().contextPlaybookId;
    if (pid && !shouldUseMocks()) {
      void api.apiGet({ action: "preview", playbook_id: pid }).then((data) => {
        if (responseHasPayload(data)) applyResponse(data);
      });
    }
  }, [api, applyResponse, checkBridgeStatus, loadPatternCatalog]);

  useEffect(() => {
    void refreshInvestigationContext();
  }, [
    refreshInvestigationContext,
    urlCtx.containerId,
    urlCtx.eventId,
    urlCtx.investigationId,
    urlCtx.ruleName,
  ]);

  useEffect(() => {
    if (personaMode === "coach" || personaMode === "tutor" || personaMode === "assistant") {
      void refreshCoachSuggest();
    }
  }, [
    personaMode,
    refreshCoachSuggest,
    urlCtx.containerId,
    urlCtx.eventId,
    urlCtx.ruleName,
  ]);

  const workflowStep = useMemo((): WorkflowStep => {
    if (urlCtx.containerId && linkedPlaybookId) return 4;
    if (linkedPlaybookId) return 3;
    if (draftReady || preview.length > 0 || currentSource) return 2;
    return 1;
  }, [currentSource, draftReady, linkedPlaybookId, preview.length, urlCtx.containerId]);

  const ctxLabel = useMemo(() => {
    const bits: string[] = [];
    if (linkedPlaybookId) bits.push(`Playbook ${linkedPlaybookId}`);
    if (urlCtx.containerId) bits.push(`Case ${urlCtx.containerId}`);
    if (urlCtx.eventId) bits.push(`Event ${urlCtx.eventId}`);
    if (investigationContext?.cef?.user) bits.push(`User ${investigationContext.cef.user}`);
    if (bits.length === 0 && instructions) return instructions;
    return bits.join(" · ") || "Draft a playbook with natural language";
  }, [instructions, investigationContext, linkedPlaybookId, urlCtx.containerId, urlCtx.eventId]);

  const bridgeLabel =
    bridgeOk === true && llmConfigured === true
      ? "AI connected"
      : bridgeOk === true
        ? "Bridge online · no LLM"
        : bridgeOk === false
          ? "Offline mode"
          : "Checking bridge…";
  const bridgeTitle =
    bridgeOk === true && llmConfigured === true
      ? "MCP bridge reachable and LLM configured — custom natural-language playbooks use your model API."
      : bridgeOk === true
        ? "MCP bridge is reachable but OPENAI_API_KEY / OPENAI_BASE_URL is not configured on the bridge host — custom NL prompts return stubs or keyword templates only."
        : bridgeOk === false
          ? "MCP bridge unreachable from SOAR — template library still works without AI."
          : "Probing MCP bridge and LLM readiness from the SOAR server…";
  const bridgeTone: "ok" | "warn" | "muted" =
    bridgeOk === true && llmConfigured === true
      ? "ok"
      : bridgeOk === false
        ? "warn"
        : bridgeOk === true
          ? "warn"
          : "muted";

  const hasImportedPlaybook = Boolean(linkedPlaybookId || urlCtx.contextPlaybookId);
  const canRunOnContainer = Boolean(hasImportedPlaybook && (urlCtx.containerId || usingMocks));
  const canRunReadiness = draftReady;
  const runDisabledReason = !urlCtx.containerId
    ? "Link a case first — use the case picker, ES drilldown, or container_id in the URL"
    : !hasImportedPlaybook
      ? "Import on Build tab first — Load template → Import to SOAR (or open sidecar with playbook_id after import)"
      : busy
        ? "Please wait…"
        : undefined;
  const readinessDisabledReason = !draftReady
    ? "Load a draft first — Build tab → Templates → Load template (Readiness checks Python before import)"
    : !currentSource
      ? "No playbook source in preview — load a template or scaffold a draft on Build"
      : busy
        ? "Please wait…"
        : undefined;

  const openHref = linkedPlaybookId
    ? (soarLinks?.vpe ||
        soarLinks?.open ||
        soarLinks?.playbooks_search ||
        `${urlCtx.origin}/playbook/${linkedPlaybookId}?editor=visual`)
    : "#";

  const soarHint = linkedPlaybookId
    ? `Imported — Open in SOAR opens the Visual Editor for "${linkedPlaybookSearch || linkedPlaybookSlug}"`
    : draftReady
      ? "Draft ready — import into SOAR"
      : "Ask for a playbook to see a draft";

  const value: BuilderContextValue = {
    urlCtx,
    handlerBase,
    instructions,
    linkedPlaybookId,
    linkedPlaybookName,
    linkedPlaybookSlug,
    linkedPlaybookSearch,
    draftLabel,
    currentPattern,
    setCurrentPattern,
    currentSource,
    draftReady,
    busy,
    activePreviewTab,
    setActivePreviewTab,
    preview,
    scoreLabel,
    syncStatus,
    messages,
    input,
    setInput,
    bridgeOk,
    llmConfigured,
    importSteps,
    importAttempts,
    showImportLog,
    soarLinks,
    assetPreflight,
    assetSelections,
    setAssetSelections,
    showAssetPanel,
    troubleshooting,
    setTroubleshooting,
    wizardScenarioId,
    setWizardScenarioId,
    wizardCollapsed,
    setWizardCollapsed,
    showHelp,
    setShowHelp,
    helpQuery,
    setHelpQuery,
    helpEntries,
    helpLoading,
    patterns,
    orgTemplateCount,
    patternsByCategory,
    investigationContext,
    readiness,
    messagesEndRef,
    workflowStep,
    ctxLabel,
    bridgeLabel,
    bridgeTitle,
    bridgeTone,
    canRunOnContainer,
    runDisabledReason,
    canRunReadiness,
    readinessDisabledReason,
    hasImportedPlaybook,
    openHref,
    soarHint,
    addMsg,
    sendMessage,
    handleImport,
    handleRunOnContainer,
    handleAssetConfirm,
    handleScaffold,
    handleValidate,
    handleReadinessCheck,
    handleApplyReadinessFixes,
    handleWizardStart,
    fetchHelp,
    linkCase,
    provisionDemoCase,
    provisioningCaseId,
    apiGet: api.apiGet,
    checkBridgeStatus,
    handleFixEnvironment,
    handleSetupAction,
    fixingEnvironment,
    envRefreshToken,
    usingMocks,
    personaMode,
    coachTab,
    setCoachTab,
    coachSuggest,
    coachLoading,
    refreshCoachSuggest,
  };

  return <BuilderContext.Provider value={value}>{children}</BuilderContext.Provider>;
}
