"""Risk classification and audit evidence for REST-handler actions.

SOAR owns authentication and authorization for the handler route.  Until the
live platform's request principal/role contract is verified, this module
records only privacy-safe evidence and never trusts caller-supplied role
headers as authorization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ActionPolicy:
    risk: str
    required_role: str
    mutates_soar: bool = False


@dataclass(frozen=True)
class ActionDecision:
    action: str
    risk: str
    required_role: str
    mutates_soar: bool
    enforcement: str
    allowed: bool
    authenticated_principal_observed: bool
    credential_transport_observed: tuple[str, ...]
    role_verified: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["credential_transport_observed"] = list(
            self.credential_transport_observed
        )
        return payload


_READ = ActionPolicy("read", "authenticated_user")
_DRAFT = ActionPolicy("draft", "authenticated_user")
_WRITE = ActionPolicy("write", "analyst", mutates_soar=True)
_EXECUTE = ActionPolicy("execute", "operator", mutates_soar=True)
_ADMIN = ActionPolicy("admin", "administrator", mutates_soar=True)
_ADMIN_READ = ActionPolicy("admin_read", "administrator")

ACTION_POLICIES: dict[str, ActionPolicy] = {
    "assistant_message": _DRAFT,
    "bridge_status": _ADMIN_READ,
    "coach_suggest": _DRAFT,
    "environment_check": _ADMIN_READ,
    "export_asset_config": _ADMIN_READ,
    "get_lesson": _READ,
    "import_asset_config": _ADMIN,
    "import_draft": _WRITE,
    "investigation_context": _READ,
    "links": _READ,
    "list_cases": _READ,
    "list_lessons": _READ,
    "list_patterns": _READ,
    "list_ir_templates": _READ,
    "list_troubleshooting": _READ,
    "migrate_python39": _ADMIN,
    "poll_playbook": _READ,
    "preflight_import": _DRAFT,
    "preview": _DRAFT,
    "provision_demo_case": _WRITE,
    "proxy_chat": _DRAFT,
    "readiness_check": _DRAFT,
    "rebuild_capability_index": _ADMIN,
    "run_playbook": _EXECUTE,
    "run_self_test": _ADMIN_READ,
    "scaffold": _DRAFT,
    "steps": _READ,
    "template_manifest": _READ,
    "trusted_ir_review": _DRAFT,
    "trusted_ir_template_review": _DRAFT,
    "trusted_retrieve": _READ,
    "troubleshoot": _READ,
    "validate": _DRAFT,
    "apply_environment_fixes": _ADMIN,
}


def action_policy(action: str | None) -> ActionPolicy:
    """Return policy for an action; unknown actions require administrator review."""
    normalized = str(action or "assistant_message").strip().lower()
    return ACTION_POLICIES.get(normalized, _ADMIN)


def _is_authenticated_user(user: Any) -> bool:
    if user is None:
        return False
    value = getattr(user, "is_authenticated", False)
    try:
        return bool(value() if callable(value) else value)
    except Exception:  # noqa: BLE001
        return False


def evaluate_action_request(
    request: Any,
    action: str | None,
    *,
    enforcement: str = "audit",
) -> ActionDecision:
    """Classify a request without exposing credentials or trusting role headers.

    ``audit`` is the only supported enforcement mode until live SOAR role
    evidence has been characterized.  A future enforced mode must use a
    platform-authenticated principal, not HTTP_X_* role claims.
    """
    normalized = str(action or "assistant_message").strip().lower()
    policy = action_policy(normalized)
    metadata = getattr(request, "META", {}) or {}
    transports: list[str] = []
    if metadata.get("HTTP_AUTHORIZATION"):
        transports.append("authorization_header")
    if metadata.get("HTTP_X_AUTH_TOKEN"):
        transports.append("soar_token_header")
    if bool(getattr(request, "COOKIES", {}) or {}):
        transports.append("cookie")
    principal_observed = _is_authenticated_user(getattr(request, "user", None))

    # Deliberately audit-only. Header/cookie presence is transport evidence,
    # never proof of an authenticated principal or an authorized role.
    return ActionDecision(
        action=normalized,
        risk=policy.risk,
        required_role=policy.required_role,
        mutates_soar=policy.mutates_soar,
        enforcement="audit" if enforcement != "audit" else enforcement,
        allowed=True,
        authenticated_principal_observed=principal_observed,
        credential_transport_observed=tuple(transports),
        role_verified=False,
    )
