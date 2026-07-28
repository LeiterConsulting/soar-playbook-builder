"""Runtime test fixtures per playbook template — container, artifacts, expectations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RuntimeTier = Literal["safe", "integration", "destructive"]


@dataclass
class RuntimeExpect:
    playbook_complete: bool = True
    min_notes: int = 0
    action_names: list[str] = field(default_factory=list)
    allow_action_fail: bool = False
    owner_role: str | None = None


@dataclass
class RuntimeFixture:
    pattern_id: str
    tier: RuntimeTier
    container_severity: str = "medium"
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    expect: RuntimeExpect = field(default_factory=RuntimeExpect)
    skip_runtime_without_assets: bool = False
    nl_prompt: str = ""

    def allowed_in_mode(self, mode: str) -> bool:
        if mode == "safe":
            return self.tier == "safe"
        if mode == "integration":
            return self.tier in ("safe", "integration")
        return True  # destructive mode — all tiers


RUNTIME_FIXTURES: dict[str, RuntimeFixture] = {
    "hello": RuntimeFixture(
        pattern_id="hello",
        tier="safe",
        container_severity="low",
        expect=RuntimeExpect(playbook_complete=True),
        nl_prompt="Build a minimal hello world playbook",
    ),
    "es-notable-response": RuntimeFixture(
        pattern_id="es-notable-response",
        tier="safe",
        container_severity="medium",
        artifacts=[
            {
                "name": "source_ip",
                "label": "event",
                "cef": {"sourceAddress": "203.0.113.10"},
            }
        ],
        expect=RuntimeExpect(playbook_complete=True, min_notes=1),
        nl_prompt="Build an ES notable response playbook that adds a note",
    ),
    "indicator-enrichment": RuntimeFixture(
        pattern_id="indicator-enrichment",
        tier="safe",
        artifacts=[
            {
                "name": "file_hash",
                "label": "file",
                "cef": {"fileHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
            }
        ],
        expect=RuntimeExpect(playbook_complete=True, min_notes=1),
        nl_prompt="Build indicator enrichment playbook for file hashes",
    ),
    "phishing-enrichment": RuntimeFixture(
        pattern_id="phishing-enrichment",
        tier="safe",
        artifacts=[
            {
                "name": "phish_url",
                "label": "url",
                "cef": {"requestURL": "http://203.0.113.55/malware"},
            }
        ],
        expect=RuntimeExpect(playbook_complete=True, min_notes=1),
        nl_prompt="Build phishing URL enrichment playbook",
    ),
    "failed-logins-okta": RuntimeFixture(
        pattern_id="failed-logins-okta",
        tier="destructive",
        container_severity="high",
        artifacts=[
            {
                "name": "failed_login_user",
                "label": "user",
                "cef": {
                    "user": "pb_runtime_test_user",
                    "destinationUserName": "pb_runtime_test_user",
                },
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_get_user"],
            allow_action_fail=True,
            owner_role="tier2",
        ),
        nl_prompt=(
            "Build a playbook for Access Excessive Failed Logins with Okta lookup "
            "and disable on high severity"
        ),
    ),
    "okta-idp-response": RuntimeFixture(
        pattern_id="okta-idp-response",
        tier="integration",
        container_severity="high",
        artifacts=[
            {
                "name": "idp_user",
                "label": "user",
                "cef": {
                    "user": "pb_runtime_test_user",
                    "destinationUserName": "pb_runtime_test_user",
                },
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_get_user"],
            allow_action_fail=True,
        ),
        nl_prompt="Build Okta IDP response playbook with get user and severity branch",
    ),
    "insider-threat-ad": RuntimeFixture(
        pattern_id="insider-threat-ad",
        tier="destructive",
        container_severity="high",
        artifacts=[
            {
                "name": "insider_user",
                "label": "user",
                "cef": {"user": "pb_runtime_test_user"},
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_disable_ad"],
            allow_action_fail=True,
        ),
        nl_prompt="Build insider threat playbook to disable AD user on high severity",
    ),
    "clearpass-quarantine": RuntimeFixture(
        pattern_id="clearpass-quarantine",
        tier="destructive",
        container_severity="high",
        artifacts=[
            {
                "name": "endpoint",
                "label": "event",
                "cef": {
                    "sourceAddress": "203.0.113.20",
                    "deviceCustomNumber1": 85,
                    "deviceCustomString1": "FAILED",
                },
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_get_endpoint"],
            allow_action_fail=True,
        ),
        nl_prompt="Build ClearPass quarantine playbook when risk score is 70 or higher",
    ),
    "panw-block-ip": RuntimeFixture(
        pattern_id="panw-block-ip",
        tier="destructive",
        container_severity="high",
        artifacts=[
            {
                "name": "dest_ip",
                "label": "event",
                "cef": {"destinationAddress": "203.0.113.99"},
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_block_ip"],
            allow_action_fail=True,
        ),
        nl_prompt="Build Palo Alto playbook to block destination IP from artifacts",
    ),
    "servicenow-incident": RuntimeFixture(
        pattern_id="servicenow-incident",
        tier="integration",
        container_severity="high",
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_create_incident"],
            allow_action_fail=True,
            min_notes=1,
        ),
        nl_prompt="Build ServiceNow P1 incident playbook from container severity",
    ),
    "virustotal-enrichment": RuntimeFixture(
        pattern_id="virustotal-enrichment",
        tier="integration",
        artifacts=[
            {
                "name": "hash",
                "label": "file",
                "cef": {
                    "fileHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                },
            }
        ],
        expect=RuntimeExpect(
            playbook_complete=True,
            action_names=["action_vt_query"],
            allow_action_fail=True,
            min_notes=1,
        ),
        nl_prompt="Build VirusTotal file hash enrichment playbook that closes container if malicious",
    ),
}


def fixture_for(pattern_id: str) -> RuntimeFixture | None:
    return RUNTIME_FIXTURES.get(pattern_id)


def fixtures_for_mode(mode: str) -> list[RuntimeFixture]:
    return [f for f in RUNTIME_FIXTURES.values() if f.allowed_in_mode(mode)]
