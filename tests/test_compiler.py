"""Deterministic compiler, parity, round-trip, and mocked-runtime tests."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from compiler import (  # noqa: E402
    compile_playbook,
    parse_python_ir,
    parse_visual_ir,
)
from ir.fixtures import smoke_ir_document  # noqa: E402
from ir.schema import PlaybookIR  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "compiler_smoke.sha256.json"


def _fixture_ir(*, bound_asset: bool = False) -> PlaybookIR:
    document = copy.deepcopy(smoke_ir_document())
    if bound_asset:
        action = next(node for node in document["nodes"] if node["type"] == "action")
        action["asset"] = {"kind": "asset", "name": "okta_lab"}
    return PlaybookIR.from_dict(document)


def test_compiler_is_byte_deterministic_and_matches_golden():
    ir = _fixture_ir()
    first = compile_playbook(ir)
    second = compile_playbook(ir)
    assert first.python_source == second.python_source
    assert first.visual_json() == second.visual_json()

    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert first.ir_hash == expected["ir_sha256"]
    assert (
        hashlib.sha256(first.python_source.encode("utf-8")).hexdigest()
        == expected["python_sha256"]
    )
    assert (
        hashlib.sha256(first.visual_json().encode("utf-8")).hexdigest()
        == expected["visual_json_sha256"]
    )

    reordered = smoke_ir_document()
    reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered_artifacts = compile_playbook(PlaybookIR.from_dict(reordered))
    assert reordered_artifacts.python_source == first.python_source
    assert reordered_artifacts.visual_json() == first.visual_json()


def test_python_and_visual_round_trip_losslessly():
    ir = _fixture_ir()
    artifacts = compile_playbook(ir)
    assert parse_python_ir(artifacts.python_source).to_dict(canonical=True) == ir.to_dict(
        canonical=True
    )
    assert parse_visual_ir(artifacts.visual_json()).to_dict(
        canonical=True
    ) == ir.to_dict(canonical=True)


def test_round_trip_rejects_hash_tampering():
    artifacts = compile_playbook(_fixture_ir())
    hostile_python = artifacts.python_source.replace(
        f"# IR-SHA256: {artifacts.ir_hash}",
        "# IR-SHA256: " + ("0" * 64),
        1,
    )
    try:
        parse_python_ir(hostile_python)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered Python artifact was accepted")

    hostile_visual = copy.deepcopy(artifacts.visual)
    hostile_visual["playbook_builder"]["ir_sha256"] = "0" * 64
    try:
        parse_visual_ir(hostile_visual)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered visual artifact was accepted")


def test_generated_python_ast_and_provenance_are_safe_and_complete():
    artifacts = compile_playbook(_fixture_ir())
    tree = ast.parse(artifacts.python_source)
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "eval" not in calls
    assert "exec" not in calls
    assert "compile" not in calls
    assert "importlib" not in artifacts.python_source
    assert f"# IR-SHA256: {artifacts.ir_hash}" in artifacts.python_source
    assert "# CAPABILITY-INDEX: baseline-v1" in artifacts.python_source
    assert "# GENERATED-AT: unspecified" in artifacts.python_source
    assert artifacts.python_source.count("_pb_debug(") >= 10


def test_visual_python_semantic_parity():
    ir = _fixture_ir()
    artifacts = compile_playbook(ir)
    metadata = artifacts.visual["playbook_builder"]
    assert metadata["ir_sha256"] == artifacts.ir_hash
    assert metadata["native_schema_status"] == "unverified_without_live_soar"
    assert metadata["node_inventory"] == sorted(node.id for node in ir.nodes)

    visual_nodes = artifacts.visual["coa"]["data"]["nodes"].values()
    assert {node["data"]["builderIrNodeId"] for node in visual_nodes} == {
        node.id for node in ir.nodes
    }
    visual_edges = artifacts.visual["coa"]["data"]["edges"]
    assert {
        (
            edge["builderSourceIrNode"],
            edge["builderSemantic"],
            edge["builderTargetIrNode"],
        )
        for edge in visual_edges
    } == {
        ("start", "next", "lookup_user"),
        ("lookup_user", "success", "result_present"),
        ("lookup_user", "failure", "failed"),
        ("result_present", "true", "high_risk"),
        ("result_present", "false", "failed"),
        ("high_risk", "match", "format_summary"),
        ("high_risk", "no_match", "normalize_indicator"),
        ("format_summary", "next", "merge"),
        ("normalize_indicator", "success", "merge"),
        ("normalize_indicator", "failure", "failed"),
        ("merge", "next", "approval"),
        ("approval", "success", "complete"),
        ("approval", "failure", "failed"),
        ("approval", "timeout", "failed"),
    }


class _PhantomMock:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []
        self.prompts: list[dict[str, Any]] = []
        self.debugs: list[str] = []
        self.store: dict[str, Any] = {}

    def debug(self, message: Any) -> None:
        self.debugs.append(str(message))

    def save_block_result(self, *, key: str, value: Any, auto: bool) -> None:
        assert auto is True
        self.store[key] = value

    def get_block_result(self, *, key: str) -> Any:
        return self.store.get(key)

    def collect2(self, **kwargs: Any) -> list[list[Any]]:
        path = kwargs["datapath"][0]
        values = {
            "artifact:*.cef.destinationUserName": [["analyst@example.test"]],
            "artifact:*.cef.sourceAddress": [["192.0.2.10"]],
            "container:severity": [["high"]],
            "pb_lookup_user:action_result.data.*.id": [["00u-test"]],
        }
        return values.get(path, [])

    def act(self, **kwargs: Any) -> None:
        self.actions.append(kwargs)

    def prompt2(self, **kwargs: Any) -> None:
        self.prompts.append(kwargs)


def _load_generated_playbook(
    monkeypatch: Any,
    *,
    bound_asset: bool,
) -> tuple[dict[str, Any], _PhantomMock]:
    mock = _PhantomMock()
    package = types.ModuleType("phantom")
    rules = types.ModuleType("phantom.rules")
    for name in (
        "act",
        "collect2",
        "debug",
        "get_block_result",
        "prompt2",
        "save_block_result",
    ):
        setattr(rules, name, getattr(mock, name))
    package.rules = rules
    monkeypatch.setitem(sys.modules, "phantom", package)
    monkeypatch.setitem(sys.modules, "phantom.rules", rules)

    namespace: dict[str, Any] = {}
    source = compile_playbook(_fixture_ir(bound_asset=bound_asset)).python_source
    exec(compile(source, "<generated-playbook>", "exec"), namespace)  # noqa: S102
    return namespace, mock


def test_mocked_phantom_success_path_executes_callbacks(monkeypatch: Any):
    playbook, mock = _load_generated_playbook(monkeypatch, bound_asset=True)
    container = {"id": 42, "severity": "high"}
    playbook["on_start"](container)
    assert len(mock.actions) == 1
    action = mock.actions[0]
    assert action["action"] == "get user"
    assert action["assets"] == ["okta_lab"]
    assert action["name"] == "pb_lookup_user"
    assert action["parameters"] == [{"username": "analyst@example.test"}]

    action["callback"](
        success=True,
        container=container,
        results=[{"data": [{"id": "00u-test"}]}],
    )
    assert len(mock.prompts) == 1
    prompt = mock.prompts[0]
    assert prompt["role"] == "Automation"
    assert prompt["response_types"][0]["options"]["choices"] == [
        "Approve",
        "Reject",
    ]

    prompt["callback"](
        success=True,
        container=container,
        results=[{"data": [{"response": "Approve"}]}],
    )
    assert any("complete] outcome success" in line for line in mock.debugs)
    assert any("format_summary] enter format" in line for line in mock.debugs)


def test_unbound_asset_fails_closed_without_action(monkeypatch: Any):
    playbook, mock = _load_generated_playbook(monkeypatch, bound_asset=False)
    playbook["on_start"]({"id": 42})
    assert mock.actions == []
    assert any("lookup_user] blocked asset_unbound" in line for line in mock.debugs)
    assert any("failed] outcome failure" in line for line in mock.debugs)
