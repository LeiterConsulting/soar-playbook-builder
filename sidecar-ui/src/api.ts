import type { BuilderResponse } from "./types";
import { createMockApiClient } from "./mocks/mockApiClient";

export function responseHasPayload(data: BuilderResponse | undefined): boolean {
  if (!data) return false;
  if (data.status === "error" && data.error) return true;
  return Boolean(data.preview?.length || data.source || data.content);
}

export interface UrlContext {
  contextPlaybookId: string;
  containerId: string;
  eventId: string;
  ruleName: string;
  investigationId: string;
  mode: string;
  tab: string;
  origin: string;
}

export interface ApiClientOptions {
  handlerBase: string;
  getPattern: () => string;
  getLinkedPlaybookId: () => string;
  getContextPlaybookId: () => string;
  getUrlContext: () => UrlContext;
}

function appendUrlContext(q: URLSearchParams, ctx: UrlContext) {
  if (ctx.containerId) q.set("container_id", ctx.containerId);
  if (ctx.eventId) q.set("event_id", ctx.eventId);
  if (ctx.ruleName) q.set("rule_name", ctx.ruleName);
  if (ctx.investigationId) q.set("investigation_id", ctx.investigationId);
  if (ctx.mode) q.set("mode", ctx.mode);
  if (ctx.tab) q.set("tab", ctx.tab);
}

function urlContextBody(ctx: UrlContext): Record<string, string> {
  const out: Record<string, string> = {};
  if (ctx.containerId) out.container_id = ctx.containerId;
  if (ctx.eventId) out.event_id = ctx.eventId;
  if (ctx.ruleName) out.rule_name = ctx.ruleName;
  if (ctx.investigationId) out.investigation_id = ctx.investigationId;
  return out;
}

function parseJson(text: string, status: number): BuilderResponse {
  if (status === 401) {
    return {
      status: "error",
      error_code: "SOAR_UNAUTHORIZED",
      error:
        "SOAR returned 401 Unauthorized on POST. Re-open this page from SOAR while logged in, " +
        "or your session/CSRF token may have expired. Try logging out and back into SOAR, then reload.",
      http_status: status,
    };
  }
  if (status >= 500) {
    return {
      status: "error",
      error_code: "SOAR_SERVER_ERROR",
      error: `SOAR server error (${status}). Check protected SOAR logs if this persists.`,
      http_status: status,
    };
  }
  try {
    return JSON.parse(text) as BuilderResponse;
  } catch {
    return {
      status: "error",
      error_code: "INVALID_SOAR_RESPONSE",
      error: `SOAR returned a non-JSON response (${status}). Check protected SOAR logs.`,
      http_status: status,
    };
  }
}

function readCookie(name: string): string {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return "";
}

/** SOAR/Django POSTs require CSRF token from the session cookie. */
function soarJsonHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Requested-With": "XMLHttpRequest",
  };
  const csrf = readCookie("csrftoken");
  if (csrf) {
    headers["X-CSRFToken"] = csrf;
  }
  return headers;
}

export function shouldUseMocks(): boolean {
  if (import.meta.env.VITE_USE_MOCKS === "true") return true;
  return isDevWithoutBackend();
}

export function createApiClient(opts: ApiClientOptions) {
  if (shouldUseMocks()) {
    return createMockApiClient(opts);
  }
  const api = `${opts.handlerBase}/chat`;

  async function apiGet(
    qs: Record<string, string | undefined>,
  ): Promise<BuilderResponse> {
    const q = new URLSearchParams();
    Object.entries(qs).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, v);
    });
    const pattern = opts.getPattern();
    if (pattern) q.set("pattern", pattern);

    appendUrlContext(q, opts.getUrlContext());

    const linked = opts.getLinkedPlaybookId();
    if (linked && (qs.poll || qs.action === "preview")) {
      q.set("playbook_id", linked);
    } else if (qs.action === "preview") {
      const ctx = opts.getContextPlaybookId();
      if (ctx) q.set("playbook_id", ctx);
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 25000);
    try {
      const res = await fetch(`${api}?${q.toString()}`, {
        credentials: "same-origin",
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      return parseJson(await res.text(), res.status);
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof DOMException && e.name === "AbortError") {
        return {
          status: "error",
          error:
            "Request timed out — check MCP tunnel or use Generate template.",
        };
      }
      throw e;
    }
  }

  async function apiPost(
    body: Record<string, unknown>,
    timeoutMs = 60000,
  ): Promise<BuilderResponse> {
    const payload = { ...urlContextBody(opts.getUrlContext()), ...body };
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(api, {
        method: "POST",
        credentials: "same-origin",
        headers: soarJsonHeaders(),
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      return parseJson(await res.text(), res.status);
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof DOMException && e.name === "AbortError") {
        return { status: "error", error: `Request timed out after ${timeoutMs / 1000}s` };
      }
      throw e;
    }
  }

  return {
    apiGet,
    apiPost,
    apiChat: (message: string, pattern?: string, lane?: string, source?: string) =>
      apiPost(
        {
          action: "chat",
          message,
          pattern,
          ...(lane ? { lane } : {}),
          ...(source ? { source } : {}),
        },
        90000,
      ),
    apiTroubleshoot: (query?: string) =>
      apiGet({ action: "troubleshoot", q: query || undefined }),
  };
}

/** SOAR REST handler base, e.g. /rest/handler/soarplaybookbuilder_<uuid>/mcpbridge */
export function resolveHandlerBase(): string {
  const envBase = import.meta.env.VITE_SOAR_HANDLER_BASE as string | undefined;
  if (envBase?.trim()) {
    return envBase.trim().replace(/\/+$/, "");
  }
  return window.location.pathname.replace(/\/chat.*$/, "").replace(/\/+$/, "");
}

export function isDevWithoutBackend(): boolean {
  return (
    import.meta.env.DEV &&
    !import.meta.env.VITE_SOAR_HANDLER_BASE &&
    !import.meta.env.VITE_USE_MOCKS &&
    !window.location.pathname.includes("/rest/handler/")
  );
}

export function readUrlContext(): UrlContext {
  const params = new URLSearchParams(window.location.search);
  return {
    contextPlaybookId: params.get("playbook_id") || "",
    containerId: params.get("container_id") || "",
    eventId: params.get("event_id") || "",
    ruleName: params.get("rule_name") || "",
    investigationId: params.get("investigation_id") || "",
    mode: params.get("mode") || "",
    tab: params.get("tab") || "",
    origin: window.location.origin,
  };
}
