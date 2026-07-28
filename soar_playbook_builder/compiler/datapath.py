"""Construct Splunk SOAR datapaths from structured IR bindings."""

from __future__ import annotations

from dataclasses import dataclass

from ir.schema import (
    ActionNode,
    Binding,
    DatapathBinding,
    LiteralBinding,
    Node,
    NodeOutputBinding,
)


class DatapathCompileError(ValueError):
    """A structured binding cannot be represented as a SOAR datapath."""


@dataclass(frozen=True)
class CompiledBinding:
    """Compiler-facing representation of an IR binding."""

    kind: str
    datapath: str = ""
    literal: object = None
    source_node: str = ""
    source_kind: str = ""
    path: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"kind": self.kind}
        if self.datapath:
            payload["datapath"] = self.datapath
        if self.kind == "literal":
            payload["value"] = self.literal
        if self.source_node:
            payload["source_node"] = self.source_node
        if self.source_kind:
            payload["source_kind"] = self.source_kind
        if self.path:
            payload["path"] = list(self.path)
        return payload


def action_block_name(node_id: str) -> str:
    """Return the stable SOAR block name for an action IR node."""
    return f"pb_{node_id}"


def datapath_for_binding(
    binding: DatapathBinding | NodeOutputBinding,
    *,
    nodes_by_id: dict[str, Node] | None = None,
) -> str:
    """Render a structured binding as a documented SOAR datapath."""
    if isinstance(binding, DatapathBinding):
        suffix = ".".join(binding.path)
        if binding.scope == "artifact":
            return f"artifact:*.{suffix}"
        if binding.scope == "container":
            return f"container:{suffix}"
        if binding.scope == "playbook_input":
            return f"playbook_input:{suffix}"
        raise DatapathCompileError(f"unsupported datapath scope: {binding.scope!r}")

    if nodes_by_id is None:
        raise DatapathCompileError("node output binding requires a node inventory")
    source = nodes_by_id.get(binding.source_node)
    if source is None:
        raise DatapathCompileError(
            f"node output source does not exist: {binding.source_node!r}"
        )
    if not isinstance(source, ActionNode):
        raise DatapathCompileError(
            f"{binding.source_node!r} is a local block result, not a SOAR datapath"
        )
    return (
        f"{action_block_name(binding.source_node)}:action_result."
        f"{'.'.join(binding.path)}"
    )


def compile_binding(
    binding: Binding,
    *,
    nodes_by_id: dict[str, Node],
) -> CompiledBinding:
    """Compile an IR binding without accepting free-form path strings."""
    if isinstance(binding, LiteralBinding):
        return CompiledBinding(kind="literal", literal=binding.to_dict()["value"])
    if isinstance(binding, DatapathBinding):
        return CompiledBinding(
            kind="datapath",
            datapath=datapath_for_binding(binding),
            path=binding.path,
        )
    source = nodes_by_id[binding.source_node]
    datapath = ""
    if isinstance(source, ActionNode):
        datapath = datapath_for_binding(binding, nodes_by_id=nodes_by_id)
    return CompiledBinding(
        kind="node_output",
        datapath=datapath,
        source_node=binding.source_node,
        source_kind=source.type,
        path=binding.path,
    )
