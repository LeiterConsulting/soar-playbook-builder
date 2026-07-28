/** In-app guide for growing the template library (mirrors docs/CUSTOMIZATION.md). */

const ORG_JSON_EXAMPLE = `{
  "templates": [
    {
      "id": "org-crowdstrike-isolate",
      "label": "CrowdStrike Host Isolate",
      "description": "Isolate endpoint when severity is high.",
      "tier": "destructive",
      "integrations": ["crowdstrike"],
      "nl_keywords": ["crowdstrike", "isolate host"],
      "source": "import phantom.app as phantom\\n\\ndef on_start(container):\\n    phantom.add_note(container=container, content='Isolate host', title='Org')\\n    on_finish(container)\\n\\ndef on_finish(container):\\n    phantom.debug('done')\\n"
    }
  ]
}`;

export function HelpCustomizeTemplatesGuide() {
  return (
    <div className="help-customize-guide">
      <p className="help-guide-intro">
        The template dropdown is a <strong>starter library</strong>, not a fixed catalog. Eleven
        built-in patterns ship with every install; your team can add more without rebuilding the
        app or waiting for a release.
      </p>

      <details className="help-guide-topic" open>
        <summary>
          <span className="help-guide-topic-label">Organization templates (no app rebuild)</span>
        </summary>
        <ul className="help-guide-topic-body">
          <li>
            Admins paste JSON into the Playbook Builder asset field{" "}
            <code>custom_templates_json</code>.
          </li>
          <li>
            Each template <code>id</code> must start with <code>org-</code> (e.g.{" "}
            <code>org-servicenow-bridge</code>).
          </li>
          <li>
            Templates appear in the Build tab under <strong>Organization</strong> with an{" "}
            <strong>[Org]</strong> badge. The header shows how many org templates loaded.
          </li>
          <li>
            Use for customer-specific starters, VPE exports, or air-gapped sites that cannot install
            a new <code>.tgz</code>.
          </li>
          <li>
            Invalid entries are skipped; errors show in chat when patterns load and in{" "}
            <code>org_errors</code> from <code>list_patterns</code>.
          </li>
        </ul>
        <p className="help-guide-footnote">
          Full schema and field reference: bundled{" "}
          <code>soar_playbook_builder/docs/CUSTOMIZATION.md</code> on SOAR, or the repo{" "}
          <code>docs/CUSTOMIZATION.md</code>.
        </p>
        <details className="help-guide-topic help-guide-topic-nested">
          <summary>
            <span className="help-guide-topic-label">Example org template JSON</span>
          </summary>
          <pre className="help-guide-code">{ORG_JSON_EXAMPLE}</pre>
          <p className="help-guide-footnote">
            Copy-paste starter: <code>sample_data/sample_org_templates.json</code> in the install
            package.
          </p>
        </details>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">Built-in patterns (ship to everyone)</span>
        </summary>
        <ul className="help-guide-topic-body">
          <li>
            To add a template for <em>all</em> customers in the community package, extend{" "}
            <code>builder_helpers.py</code> scaffolds and <code>pattern_catalog.py</code>, then
            rebuild with <code>./package_app.sh</code>.
          </li>
          <li>
            NL offline keywords live in the catalog — org templates can add their own via{" "}
            <code>nl_keywords</code> without a rebuild.
          </li>
          <li>
            Analysts should use Natural Language chat for one-off drafts; admins promote reviewed
            playbooks to org templates.
          </li>
        </ul>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">Migration & export</span>
        </summary>
        <ul className="help-guide-topic-body">
          <li>
            <strong>Setup assistant</strong> (Help → First-Time Setup) → Export asset config includes{" "}
            <code>custom_templates_json</code> when set.
          </li>
          <li>
            When moving SOAR instances, export asset config before shutdown and paste into the new
            asset — org templates travel with it.
          </li>
        </ul>
      </details>

      <details className="help-guide-topic">
        <summary>
          <span className="help-guide-topic-label">When NL outruns the catalog</span>
        </summary>
        <ul className="help-guide-topic-body">
          <li>
            <strong>Short-term:</strong> add an org template for the recurring workflow +{" "}
            <code>nl_keywords</code> for offline routing.
          </li>
          <li>
            <strong>Long-term:</strong> contribute a built-in scaffold if the pattern is broadly
            useful.
          </li>
          <li>See Help → Natural Language Testing & Recovery Loop → Tier 4 for the full loop.</li>
        </ul>
      </details>
    </div>
  );
}
