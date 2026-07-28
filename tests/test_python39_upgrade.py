"""Tests for python39_upgrade helpers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from python39_upgrade import phenv_path_candidates  # noqa: E402


def test_phenv_path_candidates():
    paths = phenv_path_candidates("servicenow_p1_incident", "servicenow_p1_incident/servicenow_p1_incident")
    assert "local/servicenow_p1_incident/servicenow_p1_incident" in paths
    assert "local/servicenow_p1_incident" in paths
