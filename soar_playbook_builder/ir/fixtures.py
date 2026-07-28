"""Small deterministic IR fixtures used by module gates and compiler work."""

from __future__ import annotations

from typing import Any


def smoke_ir_document() -> dict[str, Any]:
    """Return a valid document exercising every IR node type."""
    return {
        "schema_version": "1.0.0",
        "id": "all-node-smoke",
        "name": "All node smoke playbook",
        "description": "Exercises the strict IR without executing any code.",
        "entrypoint": "start",
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "next": "lookup_user",
            },
            {
                "id": "lookup_user",
                "type": "action",
                "app": "okta",
                "action": "get user",
                "asset": {"kind": "asset_unbound"},
                "parameters": {
                    "username": {
                        "kind": "datapath",
                        "scope": "artifact",
                        "path": ["cef", "destinationUserName"],
                    }
                },
                "on_success": "result_present",
                "on_failure": "failed",
            },
            {
                "id": "result_present",
                "type": "decision",
                "condition": {
                    "op": "exists",
                    "value": {
                        "kind": "node_output",
                        "source_node": "lookup_user",
                        "path": ["data", "*", "id"],
                    },
                },
                "on_true": "high_risk",
                "on_false": "failed",
            },
            {
                "id": "high_risk",
                "type": "filter",
                "condition": {
                    "op": "in",
                    "left": {
                        "kind": "datapath",
                        "scope": "container",
                        "path": ["severity"],
                    },
                    "right": {
                        "kind": "literal",
                        "value": ["high", "critical"],
                    },
                },
                "on_match": "format_summary",
                "on_no_match": "normalize_indicator",
            },
            {
                "id": "format_summary",
                "type": "format",
                "template": "Resolved user: {user_id}",
                "inputs": {
                    "user_id": {
                        "kind": "node_output",
                        "source_node": "lookup_user",
                        "path": ["data", "*", "id"],
                    }
                },
                "output": "summary",
                "next": "merge",
            },
            {
                "id": "normalize_indicator",
                "type": "code",
                "helper": "normalize_indicator",
                "arguments": {
                    "value": {
                        "kind": "datapath",
                        "scope": "artifact",
                        "path": ["cef", "sourceAddress"],
                    }
                },
                "output": "indicator",
                "on_success": "merge",
                "on_failure": "failed",
            },
            {
                "id": "merge",
                "type": "join",
                "strategy": "any",
                "next": "approval",
            },
            {
                "id": "approval",
                "type": "prompt",
                "message": "Approve the proposed response?",
                "response_key": "approval",
                "choices": ["Approve", "Reject"],
                "on_success": "complete",
                "on_failure": "failed",
                "on_timeout": "failed",
            },
            {
                "id": "complete",
                "type": "end",
                "outcome": "success",
            },
            {
                "id": "failed",
                "type": "end",
                "outcome": "failure",
            },
        ],
        "metadata": {
            "capability_index_version": "baseline-v1",
            "operating_mode": "air_gapped",
            "template_id": "ir-smoke",
            "labels": ["events"],
        },
    }
