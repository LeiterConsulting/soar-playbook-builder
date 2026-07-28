"""Strict playbook IR parser, topology, and canonicalization tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from ir.fixtures import smoke_ir_document  # noqa: E402
from ir.schema import (  # noqa: E402
    ALLOWED_CODE_HELPERS,
    IR_SCHEMA_VERSION,
    IRValidationError,
    PlaybookIR,
    ir_json_schema,
    migrate_ir_document,
)


def _issue_codes(exc: IRValidationError) -> set[str]:
    return {issue.code for issue in exc.issues}


def _node(document, node_id):
    return next(node for node in document["nodes"] if node["id"] == node_id)


def test_all_required_node_types_parse_and_roundtrip():
    document = smoke_ir_document()
    ir = PlaybookIR.from_dict(document)

    assert {node.type for node in ir.nodes} == {
        "start",
        "action",
        "decision",
        "filter",
        "format",
        "prompt",
        "code",
        "join",
        "end",
    }
    assert ir.to_dict() == document
    assert PlaybookIR.from_dict(ir.to_dict()).sha256() == ir.sha256()


def test_canonical_hash_is_independent_of_node_and_map_order():
    first = smoke_ir_document()
    second = copy.deepcopy(first)
    second["nodes"] = list(reversed(second["nodes"]))
    action = _node(second, "lookup_user")
    action["parameters"] = dict(reversed(list(action["parameters"].items())))

    assert PlaybookIR.from_dict(first).sha256() == PlaybookIR.from_dict(second).sha256()


def test_unknown_fields_and_raw_python_are_rejected():
    document = smoke_ir_document()
    action = _node(document, "lookup_user")
    action["python"] = "import os; os.system('id')"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)

    assert _issue_codes(captured.value) == {"UNKNOWN_FIELD"}


def test_code_nodes_accept_only_allowlisted_helpers():
    document = smoke_ir_document()
    code = _node(document, "normalize_indicator")
    code["helper"] = "exec_python"
    code["source"] = "print('unsafe')"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)

    # Unknown executable source is rejected before helper evaluation.
    assert _issue_codes(captured.value) == {"UNKNOWN_FIELD"}
    code.pop("source")
    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert _issue_codes(captured.value) == {"HELPER_NOT_ALLOWED"}
    assert "exec_python" not in ALLOWED_CODE_HELPERS


def test_raw_datapath_strings_are_rejected():
    document = smoke_ir_document()
    action = _node(document, "lookup_user")
    action["parameters"]["username"] = "artifact:*.cef.destinationUserName"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert _issue_codes(captured.value) == {"BINDING_REQUIRED"}


def test_dangling_edges_and_unreachable_nodes_are_reported():
    document = smoke_ir_document()
    _node(document, "start")["next"] = "missing"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert {"DANGLING_EDGE", "UNREACHABLE_NODE"} <= _issue_codes(captured.value)


def test_cycles_are_rejected_without_an_explicit_loop_construct():
    document = smoke_ir_document()
    _node(document, "approval")["on_success"] = "lookup_user"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "GRAPH_CYCLE" in _issue_codes(captured.value)


def test_node_output_must_reference_a_prior_output_node():
    document = smoke_ir_document()
    action = _node(document, "lookup_user")
    action["parameters"]["future"] = {
        "kind": "node_output",
        "source_node": "format_summary",
        "path": ["summary"],
    }

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "OUTPUT_SOURCE_NOT_PRIOR" in _issue_codes(captured.value)


def test_branch_merges_require_join_nodes():
    document = smoke_ir_document()
    _node(document, "format_summary")["next"] = "approval"
    _node(document, "normalize_indicator")["on_success"] = "approval"
    document["nodes"] = [
        node for node in document["nodes"] if node["id"] != "merge"
    ]

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "BRANCHES_REQUIRE_JOIN" in _issue_codes(captured.value)


def test_join_requires_two_distinct_predecessors():
    document = smoke_ir_document()
    _node(document, "normalize_indicator")["on_success"] = "failed"

    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "JOIN_REQUIRES_BRANCHES" in _issue_codes(captured.value)


def test_non_finite_and_oversized_literals_are_rejected():
    document = smoke_ir_document()
    condition = _node(document, "high_risk")["condition"]
    condition["right"]["value"] = float("nan")
    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "NON_FINITE_NUMBER" in _issue_codes(captured.value)

    document = smoke_ir_document()
    condition = _node(document, "high_risk")["condition"]
    condition["right"]["value"] = list(range(65))
    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(document)
    assert "LITERAL_TOO_LARGE" in _issue_codes(captured.value)


def test_schema_version_is_required_and_future_versions_fail_closed():
    missing = smoke_ir_document()
    missing.pop("schema_version")
    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(missing)
    assert "SCHEMA_VERSION_REQUIRED" in _issue_codes(captured.value)

    future = smoke_ir_document()
    future["schema_version"] = "2.0.0"
    with pytest.raises(IRValidationError) as captured:
        PlaybookIR.from_dict(future)
    assert "UNSUPPORTED_SCHEMA_VERSION" in _issue_codes(captured.value)


def test_migration_returns_detached_current_version_document():
    original = smoke_ir_document()
    migrated = migrate_ir_document(original)
    assert migrated == original
    assert migrated is not original
    migrated["name"] = "changed"
    assert original["name"] != "changed"


def test_ir_schema_is_strict_and_covers_every_node_and_helper():
    schema = ir_json_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["properties"]["schema_version"]["const"] == IR_SCHEMA_VERSION
    assert schema["additionalProperties"] is False

    node_refs = {
        row["$ref"].rsplit("/", 1)[-1]
        for row in schema["$defs"]["node"]["oneOf"]
    }
    assert node_refs == {
        "startNode",
        "actionNode",
        "decisionNode",
        "filterNode",
        "formatNode",
        "promptNode",
        "codeNode",
        "joinNode",
        "endNode",
    }
    assert schema["$defs"]["codeNode"]["properties"]["helper"]["enum"] == list(
        ALLOWED_CODE_HELPERS
    )
    for name in node_refs:
        assert schema["$defs"][name]["additionalProperties"] is False
    json.dumps(schema, allow_nan=False)


def test_emitted_schema_validates_fixture_when_jsonschema_is_available():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(ir_json_schema())
    jsonschema.validate(smoke_ir_document(), ir_json_schema())

    hostile = smoke_ir_document()
    _node(hostile, "lookup_user")["python"] = "print('not allowed')"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(hostile, ir_json_schema())
