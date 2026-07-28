"""Read-only trusted IR review service; deliberately has no import operation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from capability.schema import CapabilityIndex
from compiler import COMPILER_VERSION, compile_playbook
from ir.schema import IRValidationError, OPERATING_MODES, PlaybookIR
from retrieve import BM25Index, OfflineRetriever, SearchDocument, TemplateLibrary
from validate import preflight
from validate.render import render_gap_report

TRUSTED_REVIEW_SCHEMA_VERSION = "1.0.0"
MAX_ASSET_BINDINGS = 64
MAX_RETRIEVAL_QUERY_BYTES = 32 * 1024


@dataclass(frozen=True)
class ReviewContext:
    operating_mode: str
    evaluated_at: str
    generated_at: str
    origin: str = "manual"
    model: str = ""
    prompt_version: str = ""
    stale_after_seconds: int = 86_400

    def __post_init__(self) -> None:
        if self.operating_mode not in OPERATING_MODES:
            raise ValueError("operating_mode is not supported")
        if self.origin not in ("manual", "template", "model"):
            raise ValueError("review origin is not supported")
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")


def _stamp_document(
    document: dict[str, Any],
    index: CapabilityIndex,
    context: ReviewContext,
) -> dict[str, Any]:
    stamped = deepcopy(document)
    metadata = stamped.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        stamped["metadata"] = metadata
    metadata["capability_index_version"] = (
        index.index_version or index.version
    )
    metadata["operating_mode"] = context.operating_mode
    metadata["generated_at"] = context.generated_at
    if context.origin == "model":
        metadata["model"] = context.model
        metadata["prompt_version"] = context.prompt_version
    else:
        metadata.pop("model", None)
        metadata.pop("prompt_version", None)
    return stamped


def _apply_asset_bindings(
    document: dict[str, Any],
    asset_bindings: dict[str, str] | None,
) -> dict[str, Any]:
    if not asset_bindings:
        return document
    if not isinstance(asset_bindings, dict):
        raise ValueError("asset_bindings must be an object")
    if len(asset_bindings) > MAX_ASSET_BINDINGS:
        raise ValueError(
            f"asset_bindings exceeds {MAX_ASSET_BINDINGS} entries"
        )
    action_nodes = {
        str(node.get("id")): node
        for node in document.get("nodes") or []
        if isinstance(node, dict) and node.get("type") == "action"
    }
    unknown = sorted(set(asset_bindings) - set(action_nodes))
    if unknown:
        raise ValueError(
            f"asset binding references unknown action node: {unknown[0]}"
        )
    for node_id in sorted(asset_bindings):
        name = asset_bindings[node_id]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"asset binding for {node_id} must be a non-empty string"
            )
        action_nodes[node_id]["asset"] = {
            "kind": "asset",
            "name": name.strip(),
        }
    return document


def _issues_payload(exc: IRValidationError) -> list[dict[str, str]]:
    return [
        {
            "code": issue.code,
            "path": issue.path[:256],
        }
        for issue in exc.issues[:64]
    ]


def review_ir_document(
    document: dict[str, Any],
    index: CapabilityIndex,
    *,
    context: ReviewContext,
    asset_bindings: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate, preflight, and compile preview artifacts without importing."""
    if not isinstance(document, dict):
        return {
            "status": "error",
            "error_code": "IR_OBJECT_REQUIRED",
            "error": "IR review requires a JSON object.",
            "review_only": True,
            "import_enabled": False,
        }
    try:
        stamped = _stamp_document(document, index, context)
        stamped = _apply_asset_bindings(stamped, asset_bindings)
        ir = PlaybookIR.from_dict(stamped)
    except IRValidationError as exc:
        return {
            "status": "error",
            "error_code": "IR_INVALID",
            "error": "The document does not satisfy the Playbook IR contract.",
            "issues": _issues_payload(exc),
            "review_only": True,
            "import_enabled": False,
        }
    except ValueError as exc:
        return {
            "status": "error",
            "error_code": "REVIEW_INPUT_INVALID",
            "error": str(exc),
            "review_only": True,
            "import_enabled": False,
        }

    report = preflight(
        ir,
        index,
        evaluated_at=context.evaluated_at,
        stale_after_seconds=context.stale_after_seconds,
    )
    artifacts = compile_playbook(ir)
    python_sha256 = hashlib.sha256(
        artifacts.python_source.encode("utf-8")
    ).hexdigest()
    visual_json = artifacts.visual_json()
    visual_sha256 = hashlib.sha256(visual_json.encode("utf-8")).hexdigest()
    review_id = hashlib.sha256(
        (
            ir.sha256()
            + "\n"
            + report.canonical_json()
            + "\n"
            + COMPILER_VERSION
        ).encode("utf-8")
    ).hexdigest()
    return {
        "status": "success",
        "schema_version": TRUSTED_REVIEW_SCHEMA_VERSION,
        "review_id": review_id,
        "review_only": True,
        "import_enabled": False,
        "import_block_reason": "TRUSTED_IMPORT_DISABLED",
        "origin": context.origin,
        "ir": ir.to_dict(canonical=True),
        "ir_sha256": ir.sha256(),
        "gap_report": report.to_dict(),
        "gap_report_text": render_gap_report(report),
        "compile_eligible": report.status != "blocked",
        "ready_for_import": False,
        "compiler_version": COMPILER_VERSION,
        "artifacts": {
            "python_preview": artifacts.python_source,
            "python_sha256": python_sha256,
            "visual_preview": artifacts.visual,
            "visual_sha256": visual_sha256,
            "native_schema_status": (
                artifacts.visual.get("playbook_builder", {}).get(
                    "native_schema_status"
                )
            ),
        },
    }


def review_template(
    template_id: str,
    index: CapabilityIndex,
    *,
    context: ReviewContext,
    asset_bindings: dict[str, str] | None = None,
    library: TemplateLibrary | None = None,
) -> dict[str, Any]:
    library = library or TemplateLibrary.load()
    record = library.by_id().get(str(template_id or ""))
    if record is None:
        return {
            "status": "error",
            "error_code": "IR_TEMPLATE_NOT_FOUND",
            "error": "The requested canonical IR template was not found.",
            "review_only": True,
            "import_enabled": False,
        }
    payload = review_ir_document(
        record.ir.to_dict(),
        index,
        context=context,
        asset_bindings=asset_bindings,
    )
    if payload.get("status") == "success":
        payload["template"] = {
            "id": record.id,
            "source_sha256": record.sha256,
            "source_path": record.source_path,
        }
    return payload


def list_templates(
    query: str = "",
    *,
    limit: int = 32,
    library: TemplateLibrary | None = None,
) -> dict[str, Any]:
    if not 1 <= limit <= 64:
        raise ValueError("template list limit must be between 1 and 64")
    if len(str(query).encode("utf-8")) > MAX_RETRIEVAL_QUERY_BYTES:
        raise ValueError(
            f"template query exceeds {MAX_RETRIEVAL_QUERY_BYTES} bytes"
        )
    library = library or TemplateLibrary.load()
    if query.strip():
        index = BM25Index(
            SearchDocument(
                id=record.id,
                text=record.search_text,
                payload=record,
            )
            for record in library.records
        )
        records = [
            (row.document.payload, row.score)
            for row in index.search(query, limit=limit)
        ]
    else:
        records = [(record, None) for record in library.records[:limit]]
    return {
        "status": "success",
        "schema_version": TRUSTED_REVIEW_SCHEMA_VERSION,
        "review_only": True,
        "import_enabled": False,
        "count": len(records),
        "templates": [
            {
                "id": record.id,
                "name": record.ir.name,
                "description": record.ir.description,
                "labels": list(record.ir.metadata.labels),
                "ir_sha256": record.sha256,
                "score": round(score, 8) if score is not None else None,
            }
            for record, score in records
        ],
    }


def retrieve_candidates(
    query: str,
    index: CapabilityIndex,
    *,
    action_limit: int = 12,
    template_limit: int = 3,
    retriever: OfflineRetriever | None = None,
) -> dict[str, Any]:
    if len(str(query).encode("utf-8")) > MAX_RETRIEVAL_QUERY_BYTES:
        raise ValueError(
            f"retrieval query exceeds {MAX_RETRIEVAL_QUERY_BYTES} bytes"
        )
    bundle = (retriever or OfflineRetriever()).retrieve(
        query,
        index,
        action_limit=action_limit,
        template_limit=template_limit,
    )
    return {
        "status": "success",
        "schema_version": TRUSTED_REVIEW_SCHEMA_VERSION,
        "review_only": True,
        "import_enabled": False,
        "retrieval": bundle.context_dict(),
    }
