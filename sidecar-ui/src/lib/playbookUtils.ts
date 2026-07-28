import type { AssetPreflight, ImportStep } from "../types";

export const CLIENT_IMPORT_PHASES: ImportStep[] = [
  { id: "assets", label: "Asset preflight", status: "running" },
  { id: "package", label: "Packaging playbook files", status: "pending" },
  { id: "upload", label: "Uploading to SOAR (import_playbook)", status: "pending" },
  { id: "scm", label: "SCM sync", status: "pending" },
  { id: "resolve", label: "Resolving playbook ID", status: "pending" },
];

let msgCounter = 0;
export function nextMsgId(): string {
  msgCounter += 1;
  return String(msgCounter);
}

export function buildAssetMap(
  preflight: AssetPreflight | null | undefined,
  selections: Record<string, string>,
): Record<string, string> {
  const map: Record<string, string> = { ...(preflight?.asset_map || {}) };
  for (const req of preflight?.requirements || []) {
    if (selections[req.key]) {
      map[req.key] = selections[req.key];
    } else if (req.resolved_name) {
      map[req.key] = req.resolved_name;
    }
  }
  return map;
}

export function advanceClientImportSteps(steps: ImportStep[], phaseIndex: number): ImportStep[] {
  return steps.map((step, i) => {
    if (i < phaseIndex) return { ...step, status: "done" as const };
    if (i === phaseIndex) return { ...step, status: "running" as const };
    return { ...step, status: "pending" as const };
  });
}

export function playbookSearchSlug(name: string, pattern: string): string {
  const raw = (name || pattern || "playbook").split("/").filter(Boolean)[0] || name;
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
}

export function isDestructivePattern(
  patterns: Array<{ id: string; tier?: string; requires_confirm?: boolean }>,
  patternId: string,
): boolean {
  const row = patterns.find((p) => p.id === patternId);
  return row?.tier === "destructive" || Boolean(row?.requires_confirm);
}

export function destructiveConfirmMessage(
  patterns: Array<{ id: string; destructive_actions?: string[] }>,
  patternId: string,
): string {
  const actions = patterns.find((p) => p.id === patternId)?.destructive_actions;
  const detail = actions?.length ? actions.join(", ") : "disable users, block IPs, or quarantine endpoints";
  return (
    `This template is marked destructive and may run: ${detail}.\n\n` +
    "Only continue in a lab with test accounts. Proceed?"
  );
}
