import type { CaseSummary } from "./types";

/** Built-in demo sample cases — mirrors soar_playbook_builder/case_catalog.py */
export const DEMO_SAMPLE_CASES: CaseSummary[] = [
  {
    id: 9001,
    name: "Failed Logins — jdoe (sample)",
    severity: "high",
    status: "open",
    label: "es_notable_response",
    source: "sample",
    event_id: "sample-event-failed-logins-001",
    rule_name: "Access - Excessive Failed Logins",
    fixture_pattern_id: "failed-logins-okta",
    demo_tier: "destructive",
    summary: "user jdoe · src 10.0.0.5 · ES notable export · Okta disable (lab only)",
  },
  {
    id: 9002,
    name: "Phishing URL — finance user (sample)",
    severity: "medium",
    status: "open",
    label: "es_notable_response",
    source: "sample",
    event_id: "sample-event-phish-002",
    rule_name: "Malicious URL Click",
    fixture_pattern_id: "phishing-enrichment",
    demo_tier: "safe",
    showcase_recommended: true,
    summary: "suspicious link in email · user finance_bot · safe for demos",
  },
  {
    id: 9003,
    name: "Insider threat — critical (sample)",
    severity: "critical",
    status: "open",
    label: "ueba_insider",
    source: "sample",
    event_id: "sample-event-insider-003",
    rule_name: "Insider Threat - UEBA",
    fixture_pattern_id: "insider-threat-ad",
    demo_tier: "destructive",
    summary: "UEBA score elevated · user contractor_a · AD actions (lab only)",
  },
  {
    id: 9004,
    name: "ES Notable — suspicious source IP (sample)",
    severity: "medium",
    status: "open",
    label: "es_notable_response",
    source: "sample",
    event_id: "sample-event-es-notable-004",
    rule_name: "Suspicious Network Activity",
    fixture_pattern_id: "es-notable-response",
    demo_tier: "safe",
    showcase_recommended: true,
    summary: "ES notable export · src 203.0.113.10 · note-only playbook",
  },
  {
    id: 9005,
    name: "Hello World — minimal demo (sample)",
    severity: "low",
    status: "open",
    label: "pb_demo",
    source: "sample",
    event_id: "sample-event-hello-005",
    rule_name: "Playbook Builder Demo",
    fixture_pattern_id: "hello",
    demo_tier: "safe",
    showcase_recommended: true,
    summary: "smallest fixture · verify Run tab end-to-end with hello template",
  },
];

export function demoSampleById(id: number): CaseSummary | undefined {
  return DEMO_SAMPLE_CASES.find((row) => Number(row.id) === id);
}

export const SHOWCASE_SAMPLE_IDS = DEMO_SAMPLE_CASES.filter((c) => c.showcase_recommended).map(
  (c) => Number(c.id),
);
