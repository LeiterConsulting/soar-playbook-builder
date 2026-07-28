"""JSON Schema and llama.cpp GBNF emitters for the strict playbook IR."""

from __future__ import annotations

import json
import re
from typing import Any

from ir.schema import ir_json_schema

_KNOWN_SCHEMA_KEYWORDS = frozenset(
    {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "const",
        "description",
        "enum",
        "items",
        "maxItems",
        "maxLength",
        "maxProperties",
        "minItems",
        "minLength",
        "oneOf",
        "pattern",
        "properties",
        "propertyNames",
        "required",
        "title",
        "type",
        "uniqueItems",
    }
)

# GBNF shapes the generated JSON. The strict parser rechecks these constraints.
RUNTIME_ONLY_SCHEMA_KEYWORDS = frozenset(
    {
        "maxItems",
        "maxLength",
        "maxProperties",
        "minLength",
        "pattern",
        "propertyNames",
        "uniqueItems",
    }
)


def json_schema_text(*, indent: int = 2) -> str:
    """Return deterministic, human-readable JSON Schema."""
    return json.dumps(
        ir_json_schema(),
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def _rule_name(name: str) -> str:
    with_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    normalized = re.sub(r"[^A-Za-z0-9-]+", "-", with_boundaries)
    return normalized.strip("-").lower()


def _terminal(text: str) -> str:
    """Encode literal text as a GBNF quoted terminal."""
    return json.dumps(text, ensure_ascii=False)


def _alternatives(items: list[str]) -> str:
    if not items:
        raise ValueError("grammar alternatives must not be empty")
    if len(items) == 1:
        return items[0]
    return "(" + " | ".join(items) + ")"


class _SchemaGrammarEmitter:
    """Emit the JSON-Schema subset used by ``ir_json_schema`` as GBNF."""

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self.definitions = schema.get("$defs") or {}
        self._validate_keywords(schema, "$")

    def _validate_keywords(self, schema: Any, path: str) -> None:
        if not isinstance(schema, dict):
            return
        unknown = sorted(set(schema) - _KNOWN_SCHEMA_KEYWORDS)
        if unknown:
            raise ValueError(
                f"unsupported JSON Schema keyword at {path}: {unknown[0]}"
            )
        for container_key in ("$defs", "properties"):
            container = schema.get(container_key)
            if isinstance(container, dict):
                for name, child in container.items():
                    self._validate_keywords(
                        child,
                        f"{path}/{container_key}/{name}",
                    )
        for child_key in ("additionalProperties", "items", "propertyNames"):
            child = schema.get(child_key)
            if isinstance(child, dict):
                self._validate_keywords(child, f"{path}/{child_key}")
        for index, child in enumerate(schema.get("oneOf") or []):
            self._validate_keywords(child, f"{path}/oneOf/{index}")

    def ref_rule(self, ref: str) -> str:
        prefix = "#/$defs/"
        if not ref.startswith(prefix):
            raise ValueError(f"unsupported schema reference: {ref}")
        name = ref[len(prefix) :]
        if name not in self.definitions:
            raise ValueError(f"missing schema definition: {name}")
        return _rule_name(name)

    def fragment(self, schema: dict[str, Any]) -> str:
        if "$ref" in schema:
            return self.ref_rule(str(schema["$ref"]))
        if "const" in schema:
            return _terminal(
                json.dumps(
                    schema["const"],
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
        if "enum" in schema:
            return _alternatives(
                [
                    _terminal(
                        json.dumps(item, separators=(",", ":"), ensure_ascii=False)
                    )
                    for item in schema["enum"]
                ]
            )
        if "oneOf" in schema:
            return _alternatives(
                [self.fragment(item) for item in schema["oneOf"]]
            )

        schema_type = schema.get("type")
        if schema_type == "string":
            return "json-string"
        if schema_type == "integer":
            return "json-integer"
        if schema_type == "number":
            return "json-number"
        if schema_type == "boolean":
            return "(" + _terminal("true") + " | " + _terminal("false") + ")"
        if schema_type == "null":
            return _terminal("null")
        if schema_type == "array":
            return self.array_fragment(schema)
        if schema_type == "object":
            return self.object_fragment(schema)
        raise ValueError(f"unsupported schema fragment: {schema!r}")

    def array_fragment(self, schema: dict[str, Any]) -> str:
        item = self.fragment(schema.get("items") or {})
        content = f"{item} ({_terminal(',')} ws {item})*"
        if int(schema.get("minItems") or 0) == 0:
            content = f"({content})?"
        return f"{_terminal('[')} ws {content} ws {_terminal(']')}"

    def object_fragment(self, schema: dict[str, Any]) -> str:
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        additional = schema.get("additionalProperties", True)

        if not properties:
            if additional is False:
                return f"{_terminal('{')} ws {_terminal('}')}"
            value_schema = (
                additional
                if isinstance(additional, dict)
                else {"$ref": "#/$defs/jsonValue"}
            )
            value = self.fragment(value_schema)
            pair = f"json-string ws {_terminal(':')} ws {value}"
            pairs = f"{pair} ({_terminal(',')} ws {pair})*"
            return (
                f"{_terminal('{')} ws ({pairs})? ws {_terminal('}')}"
            )

        if additional is not False:
            raise ValueError(
                "objects with declared properties must set additionalProperties=false"
            )
        ordered = list(properties)
        optional = [name for name in ordered if name not in required]
        if len(optional) > 10:
            raise ValueError("too many optional object properties for bounded grammar")

        variants: list[str] = []
        for mask in range(1 << len(optional)):
            included_optional = {
                name
                for index, name in enumerate(optional)
                if mask & (1 << index)
            }
            selected = [
                name
                for name in ordered
                if name in required or name in included_optional
            ]
            pairs = [
                (
                    f"{_terminal(json.dumps(name, ensure_ascii=False))} ws "
                    f"{_terminal(':')} ws {self.fragment(properties[name])}"
                )
                for name in selected
            ]
            variants.append(
                f"{_terminal('{')} ws "
                + (
                    f" {_terminal(',')} ws ".join(pairs)
                    if pairs
                    else ""
                )
                + f" ws {_terminal('}')}"
            )
        return _alternatives(variants)

    def emit(self) -> str:
        root_schema = {
            key: value
            for key, value in self.schema.items()
            if key
            not in {
                "$schema",
                "$id",
                "$defs",
                "title",
                "description",
            }
        }
        lines = [
            f"root ::= ws {self.fragment(root_schema)} ws",
            r'ws ::= [ \t\n\r]*',
            (
                r'json-string ::= "\"" '
                r'([^"\\\x00-\x1F] | "\\" '
                r'(["\\/bfnrt] | "u" hex hex hex hex))* "\""'
            ),
            r"hex ::= [0-9a-fA-F]",
            r'json-integer ::= "-"? ("0" | [1-9] [0-9]*)',
            (
                r'json-number ::= json-integer '
                r'("." [0-9]+)? ([eE] [+-]? [0-9]+)?'
            ),
        ]
        for name, definition in self.definitions.items():
            lines.append(f"{_rule_name(name)} ::= {self.fragment(definition)}")
        return "\n".join(lines) + "\n"


def gbnf_grammar(schema: dict[str, Any] | None = None) -> str:
    """Generate schema-shaped GBNF suitable for llama.cpp-class runtimes.

    The grammar fixes object key order to the schema's deterministic order.
    Runtime validation still enforces lengths, regex patterns, uniqueness, and
    graph invariants that GBNF cannot express safely.
    """
    return _SchemaGrammarEmitter(schema or ir_json_schema()).emit()
