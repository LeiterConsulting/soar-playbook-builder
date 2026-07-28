"""Resolve every structured datapath against local capability evidence."""

from __future__ import annotations

from ir.schema import (
    ActionNode,
    CodeNode,
    DatapathBinding,
    FormatNode,
    NodeOutputBinding,
    PromptNode,
    node_bindings,
)

from .base import ValidationContext

_CONTAINER_FIELDS = {
    "id",
    "name",
    "label",
    "severity",
    "status",
    "owner",
    "owner_name",
    "description",
    "create_time",
    "close_time",
    "custom_fields",
}


def _check_datapath(
    binding: DatapathBinding,
    *,
    node_id: str,
    context: ValidationContext,
) -> None:
    if binding.scope == "playbook_input":
        context.add_gap(
            gap_id="PLAYBOOK_INPUT_UNDECLARED",
            severity="blocker",
            node=node_id,
            summary="IR 1.0 has no input specification for this playbook input",
            detail={"scope": binding.scope, "path": list(binding.path)},
        )
        return
    if binding.scope == "artifact":
        if len(binding.path) >= 2 and binding.path[-2] == "cef":
            field_name = binding.path[-1]
            if any(
                field.name.casefold() == field_name.casefold()
                for field in context.index.cef_fields
            ):
                return
        context.add_gap(
            gap_id="DATAPATH_UNKNOWN",
            severity="blocker",
            node=node_id,
            summary="Artifact datapath is absent from the local CEF catalog",
            detail={"scope": binding.scope, "path": list(binding.path)},
        )
        return
    root = binding.path[0]
    if root not in _CONTAINER_FIELDS:
        context.add_gap(
            gap_id="DATAPATH_UNKNOWN",
            severity="blocker",
            node=node_id,
            summary="Container datapath is not in the supported field catalog",
            detail={"scope": binding.scope, "path": list(binding.path)},
        )
    elif root == "custom_fields" and len(binding.path) > 1:
        context.add_gap(
            gap_id="DATAPATH_UNVERIFIED",
            severity="warning",
            node=node_id,
            summary="Dynamic container custom field is not inventoried",
            detail={"scope": binding.scope, "path": list(binding.path)},
        )


def _check_output(
    binding: NodeOutputBinding,
    *,
    node_id: str,
    context: ValidationContext,
) -> None:
    source = next(
        node for node in context.ir.nodes if node.id == binding.source_node
    )
    expected_path = ".".join(binding.path).casefold()
    if isinstance(source, ActionNode):
        action = context.resolved_actions.get(source.id)
        if action is None:
            return
        outputs = {
            path.casefold().removeprefix("action_result.")
            for path in action.output_datapaths
        }
        if expected_path not in outputs:
            context.add_gap(
                gap_id="OUTPUT_DATAPATH_UNKNOWN",
                severity="blocker",
                node=node_id,
                summary=(
                    f"Output path is not declared by action node {source.id!r}"
                ),
                detail={
                    "source_node": source.id,
                    "app": source.app,
                    "action": source.action,
                    "path": list(binding.path),
                    "available_outputs": sorted(action.output_datapaths),
                },
            )
        return
    output_name = (
        source.output
        if isinstance(source, FormatNode | CodeNode)
        else source.response_key
        if isinstance(source, PromptNode)
        else ""
    )
    if not binding.path or binding.path[0] != output_name:
        context.add_gap(
            gap_id="OUTPUT_DATAPATH_UNKNOWN",
            severity="blocker",
            node=node_id,
            summary=f"Local output path does not match node {source.id!r}",
            detail={
                "source_node": source.id,
                "source_type": source.type,
                "path": list(binding.path),
                "expected_root": output_name,
            },
        )


class DatapathRule:
    def run(self, context: ValidationContext) -> None:
        for node in sorted(context.ir.nodes, key=lambda item: item.id):
            for binding in node_bindings(node):
                if isinstance(binding, DatapathBinding):
                    _check_datapath(
                        binding,
                        node_id=node.id,
                        context=context,
                    )
                elif isinstance(binding, NodeOutputBinding):
                    _check_output(
                        binding,
                        node_id=node.id,
                        context=context,
                    )
