"""End-to-end no-model corpus: IR -> compiler -> preflight, with no network."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from compiler import compile_playbook, parse_python_ir, parse_visual_ir  # noqa: E402
from eval.corpus import no_model_cases  # noqa: E402
from validate import preflight  # noqa: E402
from validate.report import PREFLIGHT_GAP_IDS  # noqa: E402


def test_no_model_corpus_is_offline_complete_and_exact(monkeypatch: Any):
    def network_forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("no-model corpus attempted network access")

    monkeypatch.setattr(socket, "socket", network_forbidden)
    cases = no_model_cases()
    assert len(cases) >= 30
    assert len({case.id for case in cases}) == len(cases)
    seeded_ids = {
        gap_id for case in cases for gap_id in case.expected_gap_ids
    }
    assert seeded_ids == set(PREFLIGHT_GAP_IDS)

    for case in cases:
        artifacts = compile_playbook(case.ir)
        assert parse_python_ir(artifacts.python_source).sha256() == case.ir.sha256()
        assert parse_visual_ir(artifacts.visual).sha256() == case.ir.sha256()
        report = preflight(
            case.ir,
            case.index,
            evaluated_at=case.evaluated_at,
        )
        assert report.status == case.expected_status, case.id
        assert tuple(sorted(gap.id for gap in report.gaps)) == (
            case.expected_gap_ids
        ), case.id


def test_no_model_corpus_construction_is_deterministic():
    first = no_model_cases()
    second = no_model_cases()
    assert [case.id for case in first] == [case.id for case in second]
    assert [case.ir.sha256() for case in first] == [
        case.ir.sha256() for case in second
    ]
    assert [case.index.to_dict() for case in first] == [
        case.index.to_dict() for case in second
    ]


def test_corpus_egress_substitution_is_explicit_not_automatic():
    case = next(
        row
        for row in no_model_cases()
        if row.id == "32_virustotal_offline_substitution"
    )
    report = preflight(
        case.ir,
        case.index,
        evaluated_at=case.evaluated_at,
    )
    assert len(report.substitutions) == 1
    substitution = report.substitutions[0]
    assert substitution.source_app == "virustotalv3"
    assert substitution.replacement_app == "phantom"
    assert substitution.replacement_action == "add list"
    assert substitution.automatic is False
