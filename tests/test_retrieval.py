"""Deterministic BM25, template-library, and bounded-context tests."""

from __future__ import annotations

import copy
import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from capability.index import load_baseline_apps, load_baseline_cef  # noqa: E402
from capability.schema import CapabilityIndex  # noqa: E402
from compiler import compile_playbook, parse_python_ir, parse_visual_ir  # noqa: E402
from eval.corpus import retrieval_cases  # noqa: E402
from pattern_catalog import catalog_ids  # noqa: E402
from retrieve import (  # noqa: E402
    BM25Index,
    OfflineRetriever,
    SearchDocument,
    TemplateLibrary,
    tokenize,
)
from retrieve.hybrid import reciprocal_rank_fusion  # noqa: E402
from retrieve.templates import MAX_TEMPLATE_BYTES  # noqa: E402


def _baseline_index() -> CapabilityIndex:
    return CapabilityIndex(
        index_version="retrieval-fixture-v1",
        built_at="2026-07-28T16:00:00+00:00",
        apps=load_baseline_apps(),
        cef_fields=load_baseline_cef(),
    )


def test_tokenizer_normalizes_camel_case_identifiers_and_punctuation():
    assert tokenize("destinationUserName file_hash PANW/block-IP") == (
        "destination",
        "user",
        "name",
        "file",
        "hash",
        "panw",
        "block",
        "ip",
    )


def test_bm25_is_deterministic_and_ties_break_by_document_id():
    documents = [
        SearchDocument("z", "alpha beta"),
        SearchDocument("a", "alpha beta"),
        SearchDocument("b", "beta"),
    ]
    first = BM25Index(documents).search("alpha", limit=3)
    second = BM25Index(reversed(documents)).search("alpha", limit=3)
    assert [(row.document.id, row.score) for row in first] == [
        (row.document.id, row.score) for row in second
    ]
    assert [row.document.id for row in first[:2]] == ["a", "z"]
    assert BM25Index(documents).search("unseen-term", limit=3) == ()


def test_shipped_template_library_matches_catalog_and_dual_compiles():
    library = TemplateLibrary.load()
    assert {record.id for record in library.records} == set(catalog_ids())
    assert len(library.records) == 11
    for record in library.records:
        artifacts = compile_playbook(record.ir)
        assert parse_python_ir(artifacts.python_source).sha256() == record.sha256
        assert parse_visual_ir(artifacts.visual).sha256() == record.sha256
        assert record.ir.metadata.template_id == record.id
        assert record.source_path == f"{record.id}.json"


def test_template_loader_rejects_duplicate_keys_nonfinite_and_id_drift(
    tmp_path,
):
    (tmp_path / "duplicate.json").write_text(
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid template JSON"):
        TemplateLibrary.load(tmp_path)

    (tmp_path / "duplicate.json").unlink()
    (tmp_path / "nonfinite.json").write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid template JSON"):
        TemplateLibrary.load(tmp_path)

    source = (
        ROOT / "retrieve" / "templates" / "hello.json"
    ).read_text(encoding="utf-8")
    (tmp_path / "wrong-name.json").write_text(source, encoding="utf-8")
    (tmp_path / "nonfinite.json").unlink()
    with pytest.raises(ValueError, match="template id/path mismatch"):
        TemplateLibrary.load(tmp_path)


def test_template_loader_rejects_oversize_and_symlink(tmp_path):
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (MAX_TEMPLATE_BYTES + 1))
    with pytest.raises(ValueError, match="template exceeds"):
        TemplateLibrary.load(tmp_path)
    oversized.unlink()

    target = ROOT / "retrieve" / "templates" / "hello.json"
    link = tmp_path / "hello.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("filesystem does not support test symlinks")
    with pytest.raises(ValueError, match="regular file"):
        TemplateLibrary.load(tmp_path)


@pytest.mark.parametrize(
    ("query", "expected_action", "expected_template"),
    [
        (
            "create a P1 ServiceNow ticket for the incident",
            "servicenow:create ticket",
            "servicenow-incident",
        ),
        (
            "query VirusTotal file hash malware reputation",
            "virustotalv3:file reputation",
            "virustotal-enrichment",
        ),
        (
            "send a Slack channel message",
            "slack:send message",
            None,
        ),
        (
            "post an incident update to Microsoft Teams channel",
            "microsoft_teams:post message",
            "servicenow-incident",
        ),
    ],
)
def test_retrieval_ranks_expected_action_and_template(
    query,
    expected_action,
    expected_template,
):
    result = OfflineRetriever().retrieve(
        query,
        _baseline_index(),
        action_limit=5,
        template_limit=3,
    )
    assert result.actions[0].id == expected_action
    if expected_template is not None:
        assert expected_template in [item.id for item in result.templates]


def test_initial_intent_corpus_has_top_five_action_recall_above_threshold():
    cases = retrieval_cases()
    retriever = OfflineRetriever()
    index = _baseline_index()
    hits = 0
    for case in cases:
        result = retriever.retrieve(
            case.request,
            index,
            action_limit=5,
            template_limit=3,
        )
        hits += case.expected_action in [item.id for item in result.actions]
    assert hits / len(cases) >= 0.95


def test_context_is_bounded_and_does_not_include_full_action_catalog():
    index = _baseline_index()
    retriever = OfflineRetriever()
    total_actions = sum(len(app.actions) for app in index.apps.values())
    result = retriever.retrieve(
        "action message incident ticket reputation severity list playbook",
        index,
        action_limit=3,
        template_limit=2,
    )
    assert len(result.actions) <= 3
    assert len(result.templates) <= 2
    assert len(result.actions) < total_actions
    context = result.context_dict()
    assert len(context["actions"]) == len(result.actions)
    assert len(context["templates"]) == len(result.templates)


def test_retrieval_is_network_free_and_index_order_independent(monkeypatch):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("retrieval opened a socket")
        ),
    )
    first_index = _baseline_index()
    second_index = copy.deepcopy(first_index)
    second_index.apps = dict(reversed(list(second_index.apps.items())))
    first = OfflineRetriever().retrieve(
        "file hash reputation",
        first_index,
    ).context_dict()
    second = OfflineRetriever().retrieve(
        "file hash reputation",
        second_index,
    ).context_dict()
    assert first == second


def test_reciprocal_rank_fusion_is_deterministic_and_deduplicated():
    first = reciprocal_rank_fusion(
        [
            ["b", "a", "a", "c"],
            ["a", "b", "d"],
        ],
        limit=4,
    )
    second = reciprocal_rank_fusion(
        [
            ["b", "a", "a", "c"],
            ["a", "b", "d"],
        ],
        limit=4,
    )
    assert first == second
    assert [item[0] for item in first[:2]] == ["a", "b"]
    assert len({item[0] for item in first}) == len(first)
