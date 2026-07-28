/** UI personas — studio, assistant, coach (+ tutor entry). */

export type PersonaMode = "studio" | "assistant" | "coach" | "tutor";
export type CoachTab = "respond" | "explain" | "build";

const PERSONA_MODES = new Set<PersonaMode>(["studio", "assistant", "coach", "tutor"]);

function parsePersonaMode(raw: string | null | undefined): PersonaMode | null {
  const v = raw?.trim().toLowerCase();
  if (v === "assistant" || v === "coach" || v === "tutor") return v;
  if (v === "studio") return "studio";
  return null;
}

/** URL `mode=` wins; else asset `default_ui_mode`; else studio. */
export function resolvePersonaMode(assetDefault?: string | null): PersonaMode {
  const fromUrl = parsePersonaMode(new URLSearchParams(window.location.search).get("mode"));
  if (fromUrl && fromUrl !== "studio") return fromUrl;
  if (fromUrl === "studio") return "studio";
  const fromAsset = parsePersonaMode(assetDefault);
  if (fromAsset && fromAsset !== "studio") return fromAsset;
  return "studio";
}

export function readPersonaMode(assetDefault?: string | null): PersonaMode {
  return resolvePersonaMode(assetDefault);
}

export function readCoachTab(mode: PersonaMode = readPersonaMode()): CoachTab {
  const raw = new URLSearchParams(window.location.search).get("tab")?.trim().toLowerCase();
  if (raw === "respond" || raw === "explain" || raw === "build") return raw;
  if (mode === "tutor") return "explain";
  if (mode === "assistant") return "build";
  return "respond";
}

export function personaTitle(mode: PersonaMode): string {
  switch (mode) {
    case "assistant":
      return "Case Playbook Assistant";
    case "coach":
      return "Response Coach";
    case "tutor":
      return "Playbook Tutor";
    default:
      return "Splunk SOAR Playbook Builder";
  }
}

export function personaSubtitle(mode: PersonaMode): string {
  switch (mode) {
    case "assistant":
      return "Chat · preview · import from a linked case";
    case "coach":
      return "Respond · explain · build on this investigation";
    case "tutor":
      return "Lessons · quizzes · datapath help";
    default:
      return "";
  }
}

export function writeCoachTab(tab: CoachTab, mode: PersonaMode = readPersonaMode()) {
  const u = new URL(window.location.href);
  if (mode !== "studio") {
    u.searchParams.set("mode", mode === "tutor" ? "tutor" : mode);
  }
  u.searchParams.set("tab", tab);
  window.history.replaceState({}, "", u.toString());
}

export function coachTabLabel(tab: CoachTab): string {
  if (tab === "respond") return "Respond";
  if (tab === "explain") return "Explain";
  return "Build";
}

export function isPersonaMode(value: string | null | undefined): value is PersonaMode {
  return PERSONA_MODES.has(parsePersonaMode(value) ?? "studio");
}
