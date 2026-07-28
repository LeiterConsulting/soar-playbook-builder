import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from builder_helpers import resolve_pattern_key  # noqa: E402
from local_nl_build import match_pattern, should_defer_to_llm  # noqa: E402


PAGERDUTY_PROMPT = (
    "Build a playbook that creates a PagerDuty incident when a critical ES notable fires, "
    "posts a summary to Microsoft Teams, and holds execution until an analyst approves in the "
    "case before running any containment actions."
)


def test_match_failed_logins_okta():
    msg = "build a playbook for excessive failed logins with okta disable on high severity"
    pattern = match_pattern(msg)
    assert pattern in ("failed-logins-okta", "okta-idp-response")


def test_scaffold_legacy_alias_resolves():
    assert match_pattern("scaffold nnsa-failed-logins") == "failed-logins-okta"
    assert resolve_pattern_key("nnsa-failed-logins") == "failed-logins-okta"


def test_defer_multi_integration_prompt():
    assert should_defer_to_llm(PAGERDUTY_PROMPT) is True
    assert match_pattern(PAGERDUTY_PROMPT) == "es-notable-response"


def test_no_defer_simple_es_prompt():
    msg = "build a playbook for es notable response with a case note"
    assert should_defer_to_llm(msg) is False
    assert match_pattern(msg) == "es-notable-response"


if __name__ == "__main__":
    test_match_failed_logins_okta()
    test_scaffold_legacy_alias_resolves()
    print("ok")
