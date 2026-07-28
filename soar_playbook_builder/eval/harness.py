#!/usr/bin/env python3
"""Eval harness — gating dependency for air-gap playbook builder modules."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capability.index import (  # noqa: E402
    build_index,
    index_status,
    load_baseline_apps,
    load_baseline_cef,
    load_egress_tags,
    load_index,
    merge_baseline,
)
from capability.introspect import harvest_all  # noqa: E402
from capability.schema import CapabilityIndex  # noqa: E402
from compiler import compile_playbook, parse_python_ir, parse_visual_ir  # noqa: E402
from eval.corpus import no_model_cases, retrieval_cases  # noqa: E402
from ir.fixtures import smoke_ir_document  # noqa: E402
from ir.grammar import gbnf_grammar, json_schema_text  # noqa: E402
from ir.schema import IRValidationError, PlaybookIR, ir_json_schema  # noqa: E402
from llm.decode import GenerationContext, generate_ir  # noqa: E402
from llm.provider import ProviderError  # noqa: E402
from retrieve import OfflineRetriever, TemplateLibrary  # noqa: E402
from validate import gap_report_json_schema, preflight  # noqa: E402
from validate.fixtures import (  # noqa: E402
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
    qualified_smoke_ir,
)
from validate.report import PREFLIGHT_GAP_IDS  # noqa: E402


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def suite_capability() -> None:
    """Step 1 gate — capability index schema, baseline, merge, persistence."""
    baseline = load_baseline_apps()
    if len(baseline) < 3:
        _fail(f"baseline apps too small: {len(baseline)}")
    _ok(f"baseline apps loaded ({len(baseline)})")

    cef = load_baseline_cef()
    if len(cef) < 5:
        _fail(f"baseline cef too small: {len(cef)}")
    _ok(f"baseline cef loaded ({len(cef)} fields)")

    egress = load_egress_tags()
    if "phantom" not in egress:
        _fail("egress_tags missing phantom")
    if egress.get("virustotalv3", {}).get("file reputation") != "true":
        _fail("virustotal file reputation must require egress")
    _ok("egress tags loaded")

    # Offline harvest (no REST) should still produce baseline-backed index
    discovered = harvest_all(rest_fn=lambda *_a, **_k: (False, "offline"), baseline_cef=cef)
    empty = CapabilityIndex(
        built_at=discovered.built_at,
        harvest_status="failed",
        harvest_errors=discovered.harvest_errors,
        apps=baseline,
        assets=[],
        cef_fields=cef,
        labels=["events"],
        severities=["low", "medium", "high", "critical"],
        statuses=["new", "open", "closed"],
    )
    merged = merge_baseline(empty)
    if "pagerduty" not in merged.apps:
        _fail("merged index missing pagerduty baseline app")
    pd = merged.apps["pagerduty"]
    create = next((a for a in pd.actions if a.name == "create incident"), None)
    if not create or create.requires_egress != "true":
        _fail("pagerduty create incident egress tag wrong")
    _ok("baseline merge preserves egress tags")

    tmp = Path(__file__).resolve().parent / ".tmp_capability_index.json"
    index, saved = build_index(rest_fn=lambda *_a, **_k: (False, "offline"), persist=True, path=tmp)
    if saved is None or not saved.is_file():
        _fail("build_index did not persist")
    loaded = load_index(path=tmp)
    if loaded is None or "phantom" not in loaded.apps:
        _fail("reload index missing phantom")
    _ok(f"index persist + reload ({saved.name})")

    status = index_status(path=tmp)
    if status["app_count"] < 3:
        _fail(f"index_status app_count: {status['app_count']}")
    _ok(f"index_status app_count={status['app_count']} action_count={status['action_count']}")

    for artifact in (
        tmp,
        tmp.with_name(f"{tmp.stem}.last-good{tmp.suffix}"),
        tmp.with_name(f"{tmp.name}.lock"),
    ):
        artifact.unlink(missing_ok=True)
    print("\nSuite capability: PASS")


def suite_ir() -> None:
    """Step 2 gate — strict IR, canonicalization, schema, and grammar."""
    document = smoke_ir_document()
    ir = PlaybookIR.from_dict(document)
    node_types = {node.type for node in ir.nodes}
    expected_types = {
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
    if node_types != expected_types:
        _fail(f"IR node type coverage mismatch: {sorted(node_types)}")
    _ok(f"strict IR parsed ({len(ir.nodes)} nodes, all required types)")

    reordered = copy.deepcopy(document)
    reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered_ir = PlaybookIR.from_dict(reordered)
    if reordered_ir.sha256() != ir.sha256():
        _fail("canonical IR hash changed after node reordering")
    _ok(f"canonical IR hash stable ({ir.sha256()[:16]})")

    hostile = copy.deepcopy(document)
    action = next(node for node in hostile["nodes"] if node["type"] == "action")
    action["python"] = "import os"
    try:
        PlaybookIR.from_dict(hostile)
    except IRValidationError as exc:
        if not any(issue.code == "UNKNOWN_FIELD" for issue in exc.issues):
            _fail(f"hostile action rejected with unexpected code: {exc}")
    else:
        _fail("action node accepted a free-form Python field")
    _ok("free-form executable fields rejected")

    schema = ir_json_schema()
    if schema.get("additionalProperties") is not False:
        _fail("IR JSON Schema root is not closed")
    if len(schema.get("$defs") or {}) < 20:
        _fail("IR JSON Schema definitions are incomplete")
    schema_text = json_schema_text()
    grammar = gbnf_grammar()
    if not schema_text.strip().startswith("{"):
        _fail("JSON Schema text emitter failed")
    if not grammar.startswith("root ::="):
        _fail("GBNF root rule missing")
    if '\\"python\\"' in grammar or '\\"source\\"' in grammar:
        _fail("GBNF exposes an executable source field")
    _ok(
        f"schema + GBNF emitted ({len(schema_text)} / {len(grammar)} bytes)"
    )
    print("\nSuite ir: PASS")


def suite_compiler() -> None:
    """Step 3 gate — deterministic dual artifacts and lossless round trip."""
    ir = PlaybookIR.from_dict(smoke_ir_document())
    first = compile_playbook(ir)
    second = compile_playbook(ir)
    if first.python_source != second.python_source:
        _fail("compiler Python output is not byte deterministic")
    if first.visual_json() != second.visual_json():
        _fail("compiler visual JSON is not byte deterministic")
    _ok(f"byte-deterministic dual compile ({first.ir_hash[:16]})")

    try:
        ast.parse(first.python_source)
    except SyntaxError as exc:
        _fail(f"generated Python is invalid: {exc}")
    _ok(f"generated Python parses ({len(first.python_source)} bytes)")

    python_ir = parse_python_ir(first.python_source)
    visual_ir = parse_visual_ir(first.visual)
    if python_ir.to_dict(canonical=True) != ir.to_dict(canonical=True):
        _fail("Python artifact did not round-trip to identical IR")
    if visual_ir.to_dict(canonical=True) != ir.to_dict(canonical=True):
        _fail("visual artifact did not round-trip to identical IR")
    _ok("Python + visual artifacts round-trip losslessly")

    visual_meta = first.visual.get("playbook_builder") or {}
    if visual_meta.get("ir_sha256") != first.ir_hash:
        _fail("visual artifact IR hash does not match Python artifact")
    expected_nodes = sorted(node.id for node in ir.nodes)
    if visual_meta.get("node_inventory") != expected_nodes:
        _fail("visual artifact node inventory drifted from IR")
    visual_nodes = first.visual["coa"]["data"]["nodes"].values()
    actual_nodes = sorted(node["data"]["builderIrNodeId"] for node in visual_nodes)
    if actual_nodes != expected_nodes:
        _fail("visual COA node inventory drifted from IR")
    _ok(f"artifact hash + node parity ({len(expected_nodes)} nodes)")
    print("\nSuite compiler: PASS")


def suite_validator() -> None:
    """Step 4 gate — deterministic GapReport and seeded blockers."""
    ir = qualified_smoke_ir()
    index = qualified_smoke_index()
    clean = preflight(ir, index, evaluated_at=FIXTURE_EVALUATED_AT)
    if clean.status != "ok" or clean.gaps:
        _fail(f"fully evidenced validator fixture produced gaps: {clean.canonical_json()}")
    _ok("fully evidenced preflight has no false positive")

    missing_asset = qualified_smoke_document()
    action = next(
        node for node in missing_asset["nodes"] if node["type"] == "action"
    )
    action["asset"] = {"kind": "asset_unbound"}
    blocked = preflight(
        PlaybookIR.from_dict(missing_asset),
        index,
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    ids = {gap.id for gap in blocked.gaps}
    if blocked.status != "blocked" or "ASSET_UNBOUND" not in ids:
        _fail("known-bad asset fixture was not blocked")
    _ok("known-bad asset fixture returns ASSET_UNBOUND")

    repeat = preflight(
        PlaybookIR.from_dict(missing_asset),
        index,
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    if repeat.canonical_json() != blocked.canonical_json():
        _fail("GapReport serialization is not deterministic")
    _ok("GapReport serialization is byte deterministic")

    schema = gap_report_json_schema()
    required = set(schema.get("required") or [])
    if {
        "status",
        "gaps",
        "substitutions",
        "index_version",
        "index_age_seconds",
        "evaluated_at",
        "ir_sha256",
    } - required:
        _fail("GapReport schema is missing required fields")
    if schema.get("additionalProperties") is not False:
        _fail("GapReport root schema is not closed")
    _ok("GapReport schema is closed and complete")
    print("\nSuite validator: PASS")


def suite_corpus() -> None:
    """Step 5 gate — capability/IR/compiler/validator without a model."""
    cases = no_model_cases()
    if len(cases) < 30:
        _fail(f"no-model corpus too small: {len(cases)}")
    if len({case.id for case in cases}) != len(cases):
        _fail("no-model corpus case IDs are not unique")
    _ok(f"no-model corpus loaded ({len(cases)} cases)")

    seeded_ids: set[str] = set()
    for case in cases:
        artifacts = compile_playbook(case.ir)
        if parse_python_ir(artifacts.python_source).sha256() != case.ir.sha256():
            _fail(f"{case.id}: Python round-trip mismatch")
        if parse_visual_ir(artifacts.visual).sha256() != case.ir.sha256():
            _fail(f"{case.id}: visual round-trip mismatch")
        report = preflight(
            case.ir,
            case.index,
            evaluated_at=case.evaluated_at,
        )
        actual_ids = tuple(sorted(gap.id for gap in report.gaps))
        if report.status != case.expected_status:
            _fail(
                f"{case.id}: expected status {case.expected_status}, "
                f"got {report.status}"
            )
        if actual_ids != case.expected_gap_ids:
            _fail(
                f"{case.id}: expected gaps {case.expected_gap_ids}, "
                f"got {actual_ids}"
            )
        seeded_ids.update(actual_ids)
    _ok(f"IR + dual compile + expected gaps exact ({len(cases)}/{len(cases)})")
    if seeded_ids != set(PREFLIGHT_GAP_IDS):
        _fail(
            "corpus gap-ID coverage mismatch: missing "
            f"{sorted(set(PREFLIGHT_GAP_IDS) - seeded_ids)}"
        )
    _ok(f"all supported deterministic gaps seeded ({len(seeded_ids)})")
    print("\nSuite corpus: PASS")


class _ScriptedProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((copy.deepcopy(messages), dict(kwargs)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def suite_model_boundary() -> None:
    """Step 6 gate — constrained decode and bounded repair without a model."""
    context = GenerationContext(
        operating_mode="air_gapped",
        model="offline-scripted-eval",
        prompt_version="ir-generate-v1",
        generated_at=FIXTURE_EVALUATED_AT,
        evaluated_at=FIXTURE_EVALUATED_AT,
        max_attempts=2,
    )
    valid = json.dumps(
        qualified_smoke_document(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    secret = "RAW-MODEL-TEXT-MUST-NOT-CROSS"
    provider = _ScriptedProvider([f"not json {secret}", valid])
    repaired = generate_ir(
        provider,
        "Build the qualified fixture workflow.",
        qualified_smoke_index(),
        context=context,
    )
    if not repaired.ready_to_compile or repaired.attempts != 2:
        _fail("invalid JSON did not recover within the bounded repair loop")
    if secret in json.dumps(repaired.to_dict()):
        _fail("raw model output crossed the typed decode boundary")
    repair_message = provider.calls[1][0][-1]["content"]
    if "MODEL_JSON_INVALID" not in repair_message or secret in repair_message:
        _fail("repair feedback is not structured and sanitized")
    _ok("invalid model JSON repaired without echoing raw output")

    hallucinated = qualified_smoke_document()
    action = next(
        node for node in hallucinated["nodes"] if node["type"] == "action"
    )
    action["app"] = "invented_product"
    action["action"] = "invented action"
    provider = _ScriptedProvider(
        [
            json.dumps(hallucinated, separators=(",", ":")),
            valid,
        ]
    )
    corrected = generate_ir(
        provider,
        "Build the qualified fixture workflow.",
        qualified_smoke_index(),
        context=context,
    )
    if not corrected.ready_to_compile or corrected.attempts != 2:
        _fail("hallucinated capability did not trigger deterministic repair")
    if "ACTION_APP_UNKNOWN" not in provider.calls[1][0][-1]["content"]:
        _fail("preflight gap was not supplied to the bounded repair request")
    _ok("hallucinated capability rejected and corrected")

    provider = _ScriptedProvider(
        [
            ProviderError("TRANSPORT_FAILED", f"secret={secret}"),
            ProviderError("TRANSPORT_FAILED", f"secret={secret}"),
        ]
    )
    failed = generate_ir(
        provider,
        "Build the qualified fixture workflow.",
        qualified_smoke_index(),
        context=context,
    )
    failed_ids = {gap.id for gap in failed.report.gaps}
    if failed_ids != {"MODEL_PROVIDER_FAILED"}:
        _fail(f"provider failure gaps are wrong: {sorted(failed_ids)}")
    if secret in failed.report.canonical_json():
        _fail("provider exception detail leaked into GapReport")
    _ok("provider failure is bounded, blocked, and sanitized")
    print("\nSuite model_boundary: PASS")


def suite_retrieval() -> None:
    """Step 7 gate — offline BM25 and canonical IR template exemplars."""
    library = TemplateLibrary.load()
    if len(library.records) != 11:
        _fail(f"expected 11 shipped IR templates, got {len(library.records)}")
    for record in library.records:
        artifacts = compile_playbook(record.ir)
        if parse_python_ir(artifacts.python_source).sha256() != record.sha256:
            _fail(f"{record.id}: Python template round-trip mismatch")
        if parse_visual_ir(artifacts.visual).sha256() != record.sha256:
            _fail(f"{record.id}: visual template round-trip mismatch")
    _ok("11 shipped templates parse and dual-compile from canonical IR")

    index = CapabilityIndex(
        index_version="retrieval-eval-v1",
        built_at=FIXTURE_EVALUATED_AT,
        apps=load_baseline_apps(),
        cef_fields=load_baseline_cef(),
    )
    retriever = OfflineRetriever(library)
    cases = retrieval_cases()
    hits = 0
    for case in cases:
        result = retriever.retrieve(
            case.request,
            index,
            action_limit=5,
            template_limit=3,
        )
        hits += case.expected_action in [item.id for item in result.actions]
    recall = hits / len(cases)
    if recall < 0.95:
        _fail(f"top-5 action recall {recall:.3f} is below 0.95")
    _ok(f"fixed lexical intent top-5 action recall={recall:.3f}")

    total_actions = sum(len(app.actions) for app in index.apps.values())
    bounded = retriever.retrieve(
        "action message incident ticket reputation severity list playbook",
        index,
        action_limit=3,
        template_limit=2,
    )
    if len(bounded.actions) > 3 or len(bounded.templates) > 2:
        _fail("retrieval exceeded its explicit context limits")
    if len(bounded.actions) >= total_actions:
        _fail("retrieval returned the full action catalog")
    _ok("retrieval context is bounded and excludes the full catalog")

    original_socket = socket.socket
    try:
        socket.socket = lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("retrieval opened a socket")
        )
        retriever.retrieve(
            "VirusTotal file hash reputation",
            index,
            action_limit=5,
            template_limit=3,
        )
    finally:
        socket.socket = original_socket
    _ok("retrieval completes with socket creation denied")
    print("\nSuite retrieval: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="SOAR Playbook Builder eval harness")
    parser.add_argument(
        "--suite",
        default="capability",
        choices=[
            "capability",
            "ir",
            "compiler",
            "validator",
            "corpus",
            "model_boundary",
            "retrieval",
            "all",
        ],
    )
    args = parser.parse_args()
    if args.suite in ("capability", "all"):
        suite_capability()
    if args.suite in ("ir", "all"):
        suite_ir()
    if args.suite in ("compiler", "all"):
        suite_compiler()
    if args.suite in ("validator", "all"):
        suite_validator()
    if args.suite in ("corpus", "all"):
        suite_corpus()
    if args.suite in ("model_boundary", "all"):
        suite_model_boundary()
    if args.suite in ("retrieval", "all"):
        suite_retrieval()


if __name__ == "__main__":
    main()
