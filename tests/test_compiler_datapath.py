"""Structured datapath compiler tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from compiler.datapath import (  # noqa: E402
    DatapathCompileError,
    compile_binding,
    datapath_for_binding,
)
from ir.schema import (  # noqa: E402
    DatapathBinding,
    NodeOutputBinding,
    PlaybookIR,
)
from ir.fixtures import smoke_ir_document  # noqa: E402


def test_structured_soar_datapaths():
    assert (
        datapath_for_binding(DatapathBinding("artifact", ("cef", "sourceAddress")))
        == "artifact:*.cef.sourceAddress"
    )
    assert (
        datapath_for_binding(DatapathBinding("container", ("custom_fields", "owner")))
        == "container:custom_fields.owner"
    )
    assert (
        datapath_for_binding(DatapathBinding("playbook_input", ("indicator",)))
        == "playbook_input:indicator"
    )


def test_action_output_is_named_action_result_datapath():
    ir = PlaybookIR.from_dict(smoke_ir_document())
    nodes = {node.id: node for node in ir.nodes}
    binding = NodeOutputBinding("lookup_user", ("data", "*", "id"))
    compiled = compile_binding(binding, nodes_by_id=nodes)
    assert compiled.datapath == "pb_lookup_user:action_result.data.*.id"
    assert compiled.source_kind == "action"


def test_local_output_is_run_scoped_not_fabricated_datapath():
    ir = PlaybookIR.from_dict(smoke_ir_document())
    nodes = {node.id: node for node in ir.nodes}
    binding = NodeOutputBinding("format_summary", ("summary",))
    compiled = compile_binding(binding, nodes_by_id=nodes)
    assert compiled.datapath == ""
    assert compiled.source_kind == "format"
    try:
        datapath_for_binding(binding, nodes_by_id=nodes)
    except DatapathCompileError:
        pass
    else:
        raise AssertionError("local output was incorrectly rendered as a SOAR datapath")
