"""Public artifact contract and lossless compiler round-trip helpers."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from ir.schema import PlaybookIR

from .render_python import render_python
from .render_visual import render_visual

COMPILER_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "1.0.0"
_PYTHON_IR_RE = re.compile(
    r"^# PLAYBOOK-BUILDER-IR-BASE64: ([A-Za-z0-9+/=]+)$",
    re.MULTILINE,
)
_PYTHON_HASH_RE = re.compile(
    r"^# IR-SHA256: ([a-f0-9]{64})$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class CompiledPlaybook:
    """The two deterministic products of a compiler invocation."""

    python_source: str
    visual: dict[str, Any]
    ir_hash: str
    compiler_version: str = COMPILER_VERSION

    def visual_json(self) -> str:
        return json.dumps(
            self.visual,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) + "\n"


def compile_playbook(ir: PlaybookIR) -> CompiledPlaybook:
    """Compile validated IR without invoking a model or using wall-clock state."""
    python_source = render_python(
        ir,
        compiler_version=COMPILER_VERSION,
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
    )
    visual = render_visual(
        ir,
        compiler_version=COMPILER_VERSION,
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
    )
    return CompiledPlaybook(
        python_source=python_source,
        visual=visual,
        ir_hash=ir.sha256(),
    )


def parse_python_ir(source: str) -> PlaybookIR:
    """Recover and validate the canonical IR embedded in generated Python."""
    match = _PYTHON_IR_RE.search(source)
    hash_match = _PYTHON_HASH_RE.search(source)
    if match is None or hash_match is None:
        raise ValueError("generated Python does not contain embedded IR metadata")
    try:
        raw = base64.b64decode(match.group(1), validate=True).decode("utf-8")
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("generated Python contains invalid embedded IR") from exc
    ir = PlaybookIR.from_dict(document)
    if ir.sha256() != hash_match.group(1):
        raise ValueError("generated Python IR hash mismatch")
    return ir


def parse_visual_ir(document: dict[str, Any] | str) -> PlaybookIR:
    """Recover and validate IR from the visual artifact envelope."""
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except json.JSONDecodeError as exc:
            raise ValueError("visual artifact is not valid JSON") from exc
    try:
        metadata = document["playbook_builder"]
        ir_document = metadata["ir"]
        expected_hash = metadata["ir_sha256"]
    except (KeyError, TypeError) as exc:
        raise ValueError("visual artifact lacks playbook_builder IR metadata") from exc
    ir = PlaybookIR.from_dict(ir_document)
    if ir.sha256() != expected_hash:
        raise ValueError("visual artifact IR hash mismatch")
    return ir
