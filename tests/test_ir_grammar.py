"""Generated schema text and GBNF drift/shape tests."""

from __future__ import annotations

import re
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

import pytest

from ir.grammar import (  # noqa: E402
    RUNTIME_ONLY_SCHEMA_KEYWORDS,
    gbnf_grammar,
    json_schema_text,
)
from ir.schema import ALLOWED_CODE_HELPERS, ir_json_schema  # noqa: E402


def _grammar_references(grammar: str) -> tuple[set[str], set[str]]:
    defined = {
        match.group(1)
        for match in re.finditer(r"(?m)^([a-z][a-z0-9-]*)\s*::=", grammar)
    }
    referenced: set[str] = set()
    for line in grammar.splitlines():
        if "::=" not in line:
            continue
        rhs = line.split("::=", 1)[1]
        rhs = re.sub(r'"(?:\\.|[^"\\])*"', " ", rhs)
        rhs = re.sub(r"\[[^\]]*\]", " ", rhs)
        referenced.update(re.findall(r"\b[a-z][a-z0-9-]*\b", rhs))
    return defined, referenced


def test_schema_and_grammar_emission_are_deterministic():
    assert json_schema_text() == json_schema_text()
    assert gbnf_grammar() == gbnf_grammar()
    assert json_schema_text().endswith("\n")
    assert gbnf_grammar().endswith("\n")


def test_gbnf_has_no_undefined_rule_references():
    defined, referenced = _grammar_references(gbnf_grammar())
    assert "root" in defined
    assert referenced <= defined


def test_gbnf_contains_all_node_discriminators_and_helper_allowlist():
    grammar = gbnf_grammar()
    for node_type in (
        "start",
        "action",
        "decision",
        "filter",
        "format",
        "prompt",
        "code",
        "join",
        "end",
    ):
        assert f'\\"{node_type}\\"' in grammar
    for helper in ALLOWED_CODE_HELPERS:
        assert f'\\"{helper}\\"' in grammar
    assert r'\"python\"' not in grammar
    assert r'\"source\"' not in grammar


def test_gbnf_emitter_rejects_unknown_schema_features_instead_of_ignoring_them():
    schema = copy.deepcopy(ir_json_schema())
    schema["properties"]["name"]["futureUnsupportedConstraint"] = True
    with pytest.raises(ValueError, match="futureUnsupportedConstraint"):
        gbnf_grammar(schema)


def test_runtime_only_schema_constraints_are_explicit():
    assert RUNTIME_ONLY_SCHEMA_KEYWORDS == {
        "maxItems",
        "maxLength",
        "maxProperties",
        "minLength",
        "pattern",
        "propertyNames",
        "uniqueItems",
    }
