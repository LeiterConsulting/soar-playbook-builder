"""Fixed lexical intent corpus for offline top-k retrieval evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    request: str
    expected_action: str


def retrieval_cases() -> tuple[RetrievalCase, ...]:
    rows = (
        ("servicenow-create", "create ServiceNow incident ticket", "servicenow:create ticket"),
        ("servicenow-p1", "open a ServiceNow P1 ticket", "servicenow:create ticket"),
        ("servicenow-update", "update existing ServiceNow ticket fields", "servicenow:update ticket"),
        ("servicenow-id", "modify ServiceNow incident by id", "servicenow:update ticket"),
        ("vt-hash", "VirusTotal hash reputation", "virustotalv3:file reputation"),
        ("vt-malware", "malware analysis for file hash", "virustotalv3:file reputation"),
        ("vt-domain", "VirusTotal domain reputation", "virustotalv3:domain reputation"),
        ("vt-domain-malware", "check domain malware reputation", "virustotalv3:domain reputation"),
        ("slack-channel", "send a Slack channel message", "slack:send message"),
        ("slack-notify", "notify Slack with a message", "slack:send message"),
        ("teams-post", "post message to Microsoft Teams channel", "microsoft_teams:post message"),
        ("teams-notify", "notify a Teams channel by team id", "microsoft_teams:post message"),
        ("pagerduty-create", "create PagerDuty incident", "pagerduty:create incident"),
        ("pagerduty-page", "page service with PagerDuty title", "pagerduty:create incident"),
        ("phantom-note", "add a SOAR note to container", "phantom:add note"),
        ("phantom-severity", "set container severity", "phantom:set severity"),
        ("phantom-list", "append value to custom list", "phantom:add list"),
        ("phantom-child", "run child SOAR playbook", "phantom:run playbook"),
        ("phantom-execute", "execute another playbook", "phantom:run playbook"),
        ("phantom-case-severity", "change the case severity", "phantom:set severity"),
    )
    return tuple(RetrievalCase(*row) for row in rows)
