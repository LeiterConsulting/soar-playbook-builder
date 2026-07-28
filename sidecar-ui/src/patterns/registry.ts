/** Pattern registry — fallback when API unavailable; see catalog.ts */
export type { PatternDefinition } from "./catalog";
export { FALLBACK_PATTERNS, patternsFromApiPayload } from "./catalog";

import { FALLBACK_PATTERNS, type PatternDefinition } from "./catalog";

export function listPatterns(): PatternDefinition[] {
  return [...FALLBACK_PATTERNS];
}

export function registerPattern(pattern: PatternDefinition): void {
  const idx = FALLBACK_PATTERNS.findIndex((p) => p.id === pattern.id);
  if (idx >= 0) {
    FALLBACK_PATTERNS[idx] = pattern;
  } else {
    FALLBACK_PATTERNS.push(pattern);
  }
}
