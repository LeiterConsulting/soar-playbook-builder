/** Mirrors soar_playbook_builder/local_nl_build.py for mock dev routing parity. */

const BUILD_VERBS = ["build", "create", "generate", "make", "design", "write", "author", "scaffold"];
const PLAYBOOK_NOUNS = ["playbook", "automation", "response", "workflow", "coa", "firewall"];

const PATTERN_KEYWORDS: Record<string, readonly string[]> = {
  "clearpass-quarantine": ["clearpass", "quarantine", "nac", "posture", "aruba", "cppm"],
  "es-notable-response": ["es notable", "notable response", "mission control"],
  "indicator-enrichment": ["indicator enrichment", "filehash", "file hash", "ioc"],
  "virustotal-enrichment": ["virustotal", "file hash", "filehash", "vt hash", "verdict"],
  "phishing-enrichment": ["phishing", "requesturl", "malicious url"],
  "insider-threat-ad": ["insider", "disable ad", "disable user", "ueba", "insider_threat", "active directory"],
  hello: ["hello world", "minimal playbook"],
  "servicenow-incident": ["servicenow", "service now", "snow incident", "p1 incident"],
  "okta-idp-response": [
    "okta",
    "identity provider",
    "idp",
    "get user",
    "clear session",
    "destinationusername",
  ],
  "failed-logins-okta": [
    "failed login",
    "failed logins",
    "excessive failed",
    "access - excessive",
    "brute force",
    "password spray",
  ],
};

const CUSTOM_WORKFLOW_HINTS: readonly string[] = [
  "pagerduty",
  "microsoft teams",
  " ms teams",
  "post to teams",
  "teams channel",
  "jira ticket",
  "open a jira",
  "fortinet",
  "azure ad",
  "cisco ise",
  "defender",
  "impossible travel",
  "analyst approv",
  "wait for approv",
  "hold execution",
  "until approv",
  "approval gate",
  "before running any containment",
  "three branches",
  "elif ",
];

const VENDOR_TERMS = [
  "okta",
  "servicenow",
  "snow",
  "slack",
  "palo alto",
  "panw",
  "clearpass",
  "virustotal",
  "pagerduty",
  "teams",
  "jira",
  "fortinet",
  "azure",
  "cisco",
  "defender",
];

export function isBuildIntent(message: string): boolean {
  const lower = message.trim().toLowerCase();
  if (!lower || lower.startsWith("lesson ") || lower.startsWith("quiz ") || lower.startsWith("explain ")) {
    return false;
  }
  if (lower.startsWith("scaffold ")) return true;
  const hasVerb = BUILD_VERBS.some((v) => lower.includes(v));
  const hasNoun = PLAYBOOK_NOUNS.some((n) => lower.includes(n));
  return hasVerb && (hasNoun || lower.split(/\s+/).length >= 8);
}

export function shouldDeferToLlm(message: string): boolean {
  const lower = message.trim().toLowerCase();
  if (!lower) return false;
  if (CUSTOM_WORKFLOW_HINTS.some((hint) => lower.includes(hint))) return true;
  const hits = VENDOR_TERMS.filter((term) => lower.includes(term)).length;
  return hits >= 3;
}

export function parseBuilderAction(message: string): string | null {
  const lower = message.trim().toLowerCase();
  if (lower.startsWith("scaffold ")) return lower.replace("scaffold ", "").trim();
  if (lower.startsWith("pattern ")) return lower.replace("pattern ", "").trim();
  return null;
}

export function matchPattern(message: string): string | null {
  const lower = message.trim().toLowerCase();
  if (lower.startsWith("scaffold ")) {
    return lower.replace("scaffold ", "").trim().replace(/_/g, "-") || null;
  }
  const scores: Record<string, number> = {};
  for (const [pattern, kws] of Object.entries(PATTERN_KEYWORDS)) {
    const score = kws.filter((kw) => lower.includes(kw)).length;
    if (score) scores[pattern] = score;
  }
  if (lower.includes("palo alto") || lower.includes("panw") || lower.includes("block ip")) {
    scores["panw-block-ip"] = Math.max(scores["panw-block-ip"] || 0, 2);
  }
  if (lower.includes("okta") && ["failed", "login", "brute", "idp"].some((k) => lower.includes(k))) {
    scores["failed-logins-okta"] = Math.max(scores["failed-logins-okta"] || 0, 3);
  }
  const keys = Object.keys(scores);
  if (!keys.length) return null;
  return keys.reduce((best, key) => (scores[key] > scores[best] ? key : best));
}
