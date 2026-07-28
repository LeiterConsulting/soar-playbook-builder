"""Bounded model-output decoding into trusted, preflighted Playbook IR."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from capability.schema import CapabilityIndex
from ir.grammar import gbnf_grammar
from ir.schema import (
    OPERATING_MODES,
    IRValidationError,
    PlaybookIR,
    ir_json_schema,
)
from retrieve.retriever import OfflineRetriever
from validate.preflight import preflight
from validate.remediation import remediation_for
from validate.report import Gap, GapReport

from .provider import ProviderError

MAX_GENERATION_REQUEST_BYTES = 32 * 1024
MAX_CAPABILITY_CONTEXT_BYTES = 192 * 1024
MAX_REPAIR_ATTEMPTS = 4

MODEL_REPAIRABLE_GAP_IDS = frozenset(
    {
        "ACTION_APP_UNKNOWN",
        "ACTION_NOT_FOUND",
        "ALL_JOIN_UNREACHABLE",
        "ASSET_APP_MISMATCH",
        "ASSET_MISSING",
        "ASSET_UNBOUND",
        "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
        "CONTAINS_MISMATCH",
        "CONTAINS_UNVERIFIED",
        "DATAPATH_UNKNOWN",
        "DATAPATH_UNVERIFIED",
        "DESTRUCTIVE_ACTION_REVIEW_REQUIRED",
        "EGRESS_REQUIRED",
        "OUTPUT_DATAPATH_UNKNOWN",
        "PARAMETER_REQUIRED",
        "PARAMETER_TYPE_MISMATCH",
        "PARAMETER_UNKNOWN",
        "PLAYBOOK_INPUT_UNDECLARED",
        "REFERENCED_OBJECT_MISSING",
    }
)


class IRGenerationProvider(Protocol):
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        grammar: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        seed: int | None = 0,
    ) -> str: ...


@dataclass(frozen=True)
class GenerationContext:
    operating_mode: str
    model: str
    prompt_version: str
    generated_at: str
    evaluated_at: str
    stale_after_seconds: int = 86_400
    max_attempts: int = 3
    max_tokens: int = 4096
    seed: int = 0
    retrieval_action_limit: int = 12
    retrieval_template_limit: int = 3

    def __post_init__(self) -> None:
        if self.operating_mode not in OPERATING_MODES:
            raise ValueError("operating_mode is not supported")
        if not self.model or len(self.model) > 256:
            raise ValueError("model must contain between 1 and 256 characters")
        if not self.prompt_version or len(self.prompt_version) > 128:
            raise ValueError(
                "prompt_version must contain between 1 and 128 characters"
            )
        _aware_timestamp(self.generated_at, "generated_at")
        _aware_timestamp(self.evaluated_at, "evaluated_at")
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if not 1 <= self.max_attempts <= MAX_REPAIR_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_REPAIR_ATTEMPTS}"
            )
        if not 1 <= self.max_tokens <= 16_384:
            raise ValueError("max_tokens must be between 1 and 16384")
        if not 1 <= self.retrieval_action_limit <= 32:
            raise ValueError(
                "retrieval_action_limit must be between 1 and 32"
            )
        if not 1 <= self.retrieval_template_limit <= 8:
            raise ValueError(
                "retrieval_template_limit must be between 1 and 8"
            )


@dataclass(frozen=True)
class DecodeResult:
    ir: PlaybookIR | None
    report: GapReport
    attempts: int
    ready_to_compile: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ir": self.ir.to_dict() if self.ir else None,
            "gap_report": self.report.to_dict(),
            "attempts": self.attempts,
            "ready_to_compile": self.ready_to_compile,
        }


class _DuplicateKey(ValueError):
    pass


def _aware_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _decode_json_document(raw: str) -> dict[str, Any]:
    try:
        document = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, _DuplicateKey, ValueError) as exc:
        raise IRValidationError(
            # Importing IRIssue solely here would broaden the public surface.
            # Reuse the parser's stable payload via a locally imported type.
            _json_issue(str(exc))
        ) from exc
    if not isinstance(document, dict):
        raise IRValidationError(
            _json_issue("model output root must be a JSON object")
        )
    return document


def _json_issue(message: str):
    from ir.schema import IRIssue

    return IRIssue(
        code="MODEL_JSON_INVALID",
        path="$",
        message=message[:256],
    )


def _trusted_document(
    raw: str,
    *,
    index: CapabilityIndex,
    context: GenerationContext,
) -> dict[str, Any]:
    document = _decode_json_document(raw)
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        document["metadata"] = metadata
    metadata["capability_index_version"] = (
        index.index_version or index.version
    )
    metadata["operating_mode"] = context.operating_mode
    metadata["model"] = context.model
    metadata["prompt_version"] = context.prompt_version
    metadata["generated_at"] = context.generated_at
    return document


def _base_messages(
    request: str,
    index: CapabilityIndex,
    context: GenerationContext,
    retriever: OfflineRetriever,
) -> list[dict[str, str]]:
    if not isinstance(request, str) or not request.strip():
        raise ValueError("generation request must be a non-empty string")
    if len(request.encode("utf-8")) > MAX_GENERATION_REQUEST_BYTES:
        raise ValueError(
            f"generation request exceeds {MAX_GENERATION_REQUEST_BYTES} bytes"
        )
    retrieval = retriever.retrieve(
        request,
        index,
        action_limit=context.retrieval_action_limit,
        template_limit=context.retrieval_template_limit,
    )
    retrieval_context = retrieval.context_dict()
    retrieval_context["evidence"] = {
        "harvest_status": index.harvest_status,
        "permissions_status": index.permissions_status,
        "custom_lists_status": index.custom_lists_status,
        "playbooks_status": index.playbooks_status,
    }
    catalog = json.dumps(
        retrieval_context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(catalog.encode("utf-8")) > MAX_CAPABILITY_CONTEXT_BYTES:
        raise ValueError(
            f"capability context exceeds {MAX_CAPABILITY_CONTEXT_BYTES} bytes"
        )
    user_payload = json.dumps(
        {
            "request": request,
            "operating_mode": context.operating_mode,
            "capabilities": json.loads(catalog),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return [
        {
            "role": "system",
            "content": (
                "Return exactly one Playbook IR 1.0.0 JSON object. Use only the "
                "provided capabilities and typed bindings. Never emit Python, "
                "shell, markdown fences, tool calls, prose, credentials, or "
                "invented apps/actions/parameters. Unavailable assets must use "
                "asset_unbound. Destructive actions require an upstream prompt."
            ),
        },
        {"role": "user", "content": user_payload},
    ]


def _bounded_detail(detail: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "action",
        "app",
        "expected",
        "field",
        "node",
        "parameter",
        "path",
        "scope",
        "source_node",
    }
    result: dict[str, Any] = {}
    for key in sorted(set(detail) & allowed):
        value = detail[key]
        if isinstance(value, str):
            result[key] = value[:256]
        elif isinstance(value, bool | int | float) or value is None:
            result[key] = value
        elif isinstance(value, list):
            result[key] = [
                str(item)[:128] for item in value[:16]
            ]
    return result


def _repair_message(
    *,
    schema_issues: tuple[Any, ...] = (),
    gaps: tuple[Gap, ...] = (),
) -> dict[str, str]:
    issues: list[dict[str, Any]] = []
    for issue in schema_issues[:32]:
        issues.append(
            {
                "kind": "schema",
                "code": str(issue.code)[:128],
                "path": str(issue.path)[:256],
            }
        )
    for gap in gaps[:32]:
        issues.append(
            {
                "kind": "preflight",
                "id": gap.id,
                "node": gap.node,
                "detail": _bounded_detail(gap.detail),
            }
        )
    return {
        "role": "user",
        "content": json.dumps(
            {
                "instruction": (
                    "Regenerate the entire JSON document and correct every "
                    "listed issue. Do not discuss the issues."
                ),
                "issues": issues,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
    }


def _index_age(
    index: CapabilityIndex,
    evaluated_at: str,
) -> int | None:
    if not index.built_at:
        return None
    try:
        built = _aware_timestamp(index.built_at, "built_at")
        evaluated = _aware_timestamp(evaluated_at, "evaluated_at")
    except ValueError:
        return None
    return max(0, int((evaluated - built).total_seconds()))


def _terminal_gap(
    gap_id: str,
    *,
    attempts: int,
    codes: list[str],
    index: CapabilityIndex,
) -> Gap:
    detail = {
        "attempts": attempts,
        "codes": sorted(set(code[:128] for code in codes))[:32],
    }
    summaries = {
        "MODEL_OUTPUT_INVALID": "Model output did not satisfy the IR contract",
        "MODEL_PROVIDER_FAILED": "Model provider failed within the bounded run",
        "MODEL_REPAIR_EXHAUSTED": "Bounded model repair attempts were exhausted",
    }
    return Gap(
        id=gap_id,
        severity="blocker",
        node="",
        summary=summaries[gap_id],
        detail=detail,
        remediation=remediation_for(gap_id, detail, index),
    )


def _terminal_report(
    *,
    index: CapabilityIndex,
    context: GenerationContext,
    attempts: int,
    terminal_id: str,
    codes: list[str],
    last_ir: PlaybookIR | None = None,
    last_report: GapReport | None = None,
) -> GapReport:
    gaps = list(last_report.gaps) if last_report else []
    if terminal_id == "MODEL_REPAIR_EXHAUSTED" and last_ir is None:
        gaps.append(
            _terminal_gap(
                "MODEL_OUTPUT_INVALID",
                attempts=attempts,
                codes=codes,
                index=index,
            )
        )
    gaps.append(
        _terminal_gap(
            terminal_id,
            attempts=attempts,
            codes=codes,
            index=index,
        )
    )
    return GapReport.build(
        gaps=gaps,
        substitutions=(
            list(last_report.substitutions) if last_report else []
        ),
        index_version=index.index_version or index.version,
        index_age_seconds=(
            last_report.index_age_seconds
            if last_report
            else _index_age(index, context.evaluated_at)
        ),
        evaluated_at=_aware_timestamp(
            context.evaluated_at,
            "evaluated_at",
        ).isoformat(),
        ir_sha256=(
            last_ir.sha256()
            if last_ir
            else hashlib.sha256(b"").hexdigest()
        ),
    )


def generate_ir(
    provider: IRGenerationProvider,
    request: str,
    index: CapabilityIndex,
    *,
    context: GenerationContext,
    retriever: OfflineRetriever | None = None,
) -> DecodeResult:
    """Generate, authoritatively stamp, parse, and preflight IR.

    Only a parsed ``PlaybookIR`` can cross the boundary. Raw model output is
    intentionally absent from the result and all terminal reports.
    """
    messages = _base_messages(
        request,
        index,
        context,
        retriever or OfflineRetriever(),
    )
    schema = ir_json_schema()
    grammar = gbnf_grammar(schema)
    issue_codes: list[str] = []
    last_ir: PlaybookIR | None = None
    last_report: GapReport | None = None
    saw_content = False

    for attempt in range(1, context.max_attempts + 1):
        try:
            raw = provider.generate(
                messages,
                schema=schema,
                grammar=grammar,
                max_tokens=context.max_tokens,
                temperature=0.0,
                seed=context.seed,
            )
            saw_content = True
        except ProviderError as exc:
            issue_codes.append(exc.code)
            if attempt < context.max_attempts:
                messages = [
                    *messages[:2],
                    _repair_message(),
                ]
                continue
            report = _terminal_report(
                index=index,
                context=context,
                attempts=attempt,
                terminal_id=(
                    "MODEL_REPAIR_EXHAUSTED"
                    if saw_content
                    else "MODEL_PROVIDER_FAILED"
                ),
                codes=issue_codes,
                last_ir=last_ir,
                last_report=last_report,
            )
            return DecodeResult(
                ir=last_ir,
                report=report,
                attempts=attempt,
                ready_to_compile=False,
            )

        try:
            document = _trusted_document(
                raw,
                index=index,
                context=context,
            )
            ir = PlaybookIR.from_dict(document)
        except IRValidationError as exc:
            issue_codes.extend(issue.code for issue in exc.issues)
            if attempt < context.max_attempts:
                messages = [
                    *messages[:2],
                    _repair_message(schema_issues=exc.issues),
                ]
                continue
            report = _terminal_report(
                index=index,
                context=context,
                attempts=attempt,
                terminal_id=(
                    "MODEL_OUTPUT_INVALID"
                    if context.max_attempts == 1
                    else "MODEL_REPAIR_EXHAUSTED"
                ),
                codes=issue_codes,
            )
            return DecodeResult(
                ir=None,
                report=report,
                attempts=attempt,
                ready_to_compile=False,
            )

        last_ir = ir
        report = preflight(
            ir,
            index,
            evaluated_at=context.evaluated_at,
            stale_after_seconds=context.stale_after_seconds,
        )
        last_report = report
        repairable = tuple(
            gap
            for gap in report.gaps
            if gap.severity == "blocker"
            and gap.id in MODEL_REPAIRABLE_GAP_IDS
        )
        if repairable and attempt < context.max_attempts:
            issue_codes.extend(gap.id for gap in repairable)
            messages = [
                *messages[:2],
                _repair_message(gaps=repairable),
            ]
            continue
        if repairable:
            issue_codes.extend(gap.id for gap in repairable)
            exhausted = _terminal_report(
                index=index,
                context=context,
                attempts=attempt,
                terminal_id="MODEL_REPAIR_EXHAUSTED",
                codes=issue_codes,
                last_ir=ir,
                last_report=report,
            )
            return DecodeResult(
                ir=ir,
                report=exhausted,
                attempts=attempt,
                ready_to_compile=False,
            )
        return DecodeResult(
            ir=ir,
            report=report,
            attempts=attempt,
            ready_to_compile=report.status != "blocked",
        )

    raise AssertionError("bounded generation loop exited unexpectedly")
