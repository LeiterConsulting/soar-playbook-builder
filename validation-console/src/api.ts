import type { ConsoleConfig, E2EReport } from "./types";

export async function fetchConfig(): Promise<ConsoleConfig> {
  const r = await fetch("/api/config");
  if (!r.ok) throw new Error(`Config failed: ${r.status}`);
  return (await r.json()) as ConsoleConfig;
}

export async function fetchHealth(): Promise<boolean> {
  try {
    const r = await fetch("/api/health");
    return r.ok;
  } catch {
    return false;
  }
}

export interface RunOptions {
  mode: "auto" | "A" | "B";
  skipImport?: boolean;
  noCleanup?: boolean;
  phases?: string[];
}

export async function runE2ESync(opts: RunOptions): Promise<E2EReport> {
  const r = await fetch("/api/e2e/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: opts.mode,
      skipImport: opts.skipImport,
      noCleanup: opts.noCleanup,
      phases: opts.phases,
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `Run failed HTTP ${r.status}`);
  }
  return (await r.json()) as E2EReport;
}

export function streamE2E(
  opts: RunOptions,
  handlers: {
    onCheck: (check: E2EReport["checks"][0]) => void;
    onDone: (report: E2EReport) => void;
    onError: (message: string) => void;
  },
): () => void {
  const controller = new AbortController();

  void (async () => {
    try {
      const r = await fetch("/api/e2e/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: opts.mode,
          skipImport: opts.skipImport,
          noCleanup: opts.noCleanup,
          phases: opts.phases,
        }),
        signal: controller.signal,
      });
      if (!r.ok || !r.body) {
        handlers.onError(`Stream failed HTTP ${r.status}`);
        return;
      }
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const block of parts) {
          const lines = block.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data = line.slice(5).trim();
          }
          if (!data) continue;
          const parsed = JSON.parse(data) as unknown;
          if (event === "check") {
            handlers.onCheck(parsed as E2EReport["checks"][0]);
          } else if (event === "done") {
            handlers.onDone(parsed as E2EReport);
          } else if (event === "error") {
            handlers.onError((parsed as { message: string }).message);
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError(String(err));
      }
    }
  })();

  return () => controller.abort();
}

export function statusIcon(status: string): string {
  switch (status) {
    case "ok":
      return "✓";
    case "warn":
      return "!";
    case "error":
      return "✗";
    case "manual":
      return "◎";
    default:
      return "–";
  }
}

export function worstPhaseStatus(
  checks: E2EReport["checks"],
  phaseId: string,
): string | null {
  const phase = checks.filter((c) => c.phase === phaseId);
  if (!phase.length) return null;
  const order = ["error", "warn", "manual", "skipped", "ok"];
  for (const s of order) {
    if (phase.some((c) => c.status === s)) return s;
  }
  return "ok";
}
