/** Help — UI personas (studio, assistant, coach, tutor). */

const PERSONAS = [
  {
    mode: "studio",
    label: "Studio (default)",
    detail: "Full Build · Run · Help — platform engineers and playbook authors.",
    url: ".../chat",
  },
  {
    mode: "assistant",
    label: "Case Playbook Assistant",
    detail: "Build-focused from a linked case — hide Run tab. ES drilldown + mode=assistant.",
    url: ".../chat?mode=assistant&container_id=…",
  },
  {
    mode: "coach",
    label: "Response Coach",
    detail: "Respond · Explain · Build lanes — template suggest from rule_name, offline tutor, then build.",
    url: ".../es_link?event_id=$event_id$&rule_name=$rule_name$&mode=coach",
  },
  {
    mode: "tutor",
    label: "Playbook Tutor",
    detail: "Explain lane first — lessons, quizzes, datapath help without LLM.",
    url: ".../chat?mode=tutor",
  },
];

export function HelpPersonasGuide() {
  return (
    <div className="help-personas-guide">
      <p className="help-guide-intro">
        One app, multiple <strong>personas</strong> via URL query <code>mode=</code> or asset{" "}
        <code>default_ui_mode</code>. Coach adds <code>tab=respond|explain|build</code>. Same
        connector, import, and ES round-trip.
      </p>
      <ul className="help-guide-topic-body">
        {PERSONAS.map((p) => (
          <li key={p.mode}>
            <strong>{p.label}</strong> — {p.detail}
            <br />
            <code className="help-persona-url">{p.url}</code>
          </li>
        ))}
      </ul>
      <p className="help-guide-footnote">
        ES Mission Control drilldown: append <code>&amp;mode=coach</code> to your existing{" "}
        <code>es_link</code> URL. Splunk Enterprise dashboards: use{" "}
        <code>splunk_link?rule_name=$name$&amp;src=$src$&amp;mode=coach</code> (see bundled{" "}
        <code>es_content/drilldown_splunk_playbook_builder.json</code>). Utility playbook{" "}
        <code>open_playbook_builder.py</code> sets <code>BUILDER_MODE</code> / <code>BUILDER_TAB</code>.
        Set asset <code>default_ui_mode</code> so analysts land in coach or assistant without a query
        param — URL <code>mode=</code> always overrides.
      </p>
    </div>
  );
}
