"""
Utility playbook: Open Playbook Builder from a SOAR case.

Calls the Playbook Builder app action ``get sidecar url`` with this case's ID
and any ES notable context from artifacts (event_id, rule_name), then adds a
case note with the clickable link.

Setup:
  1. Import open_playbook_builder.tgz (see utility_playbooks/package_utility_playbooks.py)
  2. Edit BUILDER_ASSET below to match your Playbook Builder asset name
  3. Run from a case → Playbooks tab → "Open Playbook Builder"

Optional: wire ES notable export to run this playbook on new cases, or use the
ES drilldown → es_link route (see docs/ES_SOAR_BUILDER_STITCH.md).
"""

import phantom.app as phantom

PLAYBOOK_LABEL = "open_playbook_builder"
BUILDER_ASSET = "playbook_builder"  # ← change to your Playbook Builder asset name
BUILDER_MODE = "coach"  # studio | assistant | coach | tutor — appended to sidecar URL
BUILDER_TAB = "respond"  # coach tab when BUILDER_MODE=coach: respond | explain | build


def on_start(container):
    cid = container["id"]
    phantom.debug(f"[Open Builder] case {cid}")

    params = {"container_id": cid}
    _merge_es_context_from_artifacts(container, params)

    phantom.act(
        "get sidecar url",
        parameters=params,
        assets=[BUILDER_ASSET],
        name="get_builder_url",
        callback=open_builder_cb,
    )


def _merge_es_context_from_artifacts(container, params):
    """Pull ES notable hints from CEF when this case came from ES export."""
    artifacts = phantom.collect2(
        container=container,
        datapath=[
            "artifact:*.cef.event_id",
            "artifact:*.cef.eventId",
            "artifact:*.cef.rule_name",
            "artifact:*.cef.name",
        ],
    )
    if not artifacts:
        return
    row = artifacts[0]
    event_id = row[0] or row[1]
    rule_name = row[2] or row[3]
    if event_id:
        params["event_id"] = str(event_id)
    if rule_name:
        params["rule_name"] = str(rule_name)
    if BUILDER_MODE and BUILDER_MODE != "studio":
        params["mode"] = BUILDER_MODE
    if BUILDER_TAB and BUILDER_MODE == "coach":
        params["tab"] = BUILDER_TAB


def open_builder_cb(action, success, container, results, handle):
    if not success:
        phantom.error(
            f"get sidecar url failed — is Playbook Builder installed and asset '{BUILDER_ASSET}' configured?"
        )
        on_finish(container)
        return

    url = None
    try:
        data = results[0]["action_result"]["data"]
        if data:
            url = data[0].get("sidecar_url")
    except (KeyError, IndexError, TypeError):
        url = None

    if not url:
        phantom.error("get sidecar url returned no sidecar_url")
        on_finish(container)
        return

    phantom.add_note(
        container=container,
        title="Playbook Builder",
        content=(
            "Open Playbook Builder for this case (build, import, then **Run on this case**):\n\n"
            f"{url}"
        ),
    )
    phantom.debug(f"[Open Builder] sidecar URL added to case notes")
    on_finish(container)


def on_finish(container):
    phantom.debug("[Open Builder] complete")
