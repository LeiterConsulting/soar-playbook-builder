"""Tests for handler action risk and identity evidence policy."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from action_policy import action_policy, evaluate_action_request  # noqa: E402


def _request(*, authenticated=False, metadata=None, cookies=None):
    return SimpleNamespace(
        user=SimpleNamespace(is_authenticated=authenticated),
        META=metadata or {},
        COOKIES=cookies or {},
    )


def test_mutating_actions_have_explicit_roles():
    assert action_policy("import_draft").required_role == "analyst"
    assert action_policy("run_playbook").required_role == "operator"
    assert action_policy("apply_environment_fixes").required_role == "administrator"
    assert action_policy("run_playbook").mutates_soar is True
    assert action_policy("trusted_ir_review").mutates_soar is False
    assert action_policy("trusted_ir_review").risk == "draft"
    assert action_policy("trusted_retrieve").risk == "read"


def test_unknown_action_defaults_to_admin_mutation_policy():
    policy = action_policy("future_unclassified_action")
    assert policy.required_role == "administrator"
    assert policy.mutates_soar is True


def test_audit_decision_records_presence_not_secret_values():
    request = _request(
        authenticated=True,
        metadata={
            "HTTP_AUTHORIZATION": "Bearer do-not-log",
            "HTTP_X_AUTH_TOKEN": "also-do-not-log",
            "HTTP_X_SOAR_ROLE": "administrator",
        },
        cookies={"sessionid": "secret"},
    )
    payload = evaluate_action_request(request, "run_playbook").to_dict()
    serialized = repr(payload)

    assert payload["allowed"] is True
    assert payload["enforcement"] == "audit"
    assert payload["authenticated_principal_observed"] is True
    assert payload["role_verified"] is False
    assert set(payload["credential_transport_observed"]) == {
        "authorization_header",
        "soar_token_header",
        "cookie",
    }
    assert "do-not-log" not in serialized
    assert "also-do-not-log" not in serialized
    assert "sessionid" not in serialized
    assert "HTTP_X_SOAR_ROLE" not in serialized


def test_requested_enforcement_fails_safe_to_audit_until_soar_contract_verified():
    decision = evaluate_action_request(
        _request(),
        "import_draft",
        enforcement="enforce",
    )
    assert decision.enforcement == "audit"
    assert decision.role_verified is False
