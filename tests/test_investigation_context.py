"""Tests for investigation context hydration and pattern suggestion."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from investigation_context import suggest_pattern_from_rule  # noqa: E402


def test_suggest_failed_logins():
    assert suggest_pattern_from_rule("Access - Excessive Failed Logins - ES Premier Lab") == "failed-logins-okta"


def test_suggest_insider():
    assert suggest_pattern_from_rule("Insider Threat - UEBA anomaly") == "insider-threat-ad"


def test_suggest_phishing():
    assert suggest_pattern_from_rule("Phishing URL detected") == "phishing-enrichment"


if __name__ == "__main__":
    test_suggest_failed_logins()
    test_suggest_insider()
    test_suggest_phishing()
    print("ok")
