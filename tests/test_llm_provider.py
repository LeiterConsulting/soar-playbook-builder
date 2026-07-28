"""Security policy and capability tests for the local-model boundary."""

from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from llm.provider import (  # noqa: E402
    OpenAICompatibleProvider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderPolicyError,
    ProviderResponseError,
    StdlibJSONTransport,
    validate_model_base_url,
)


class RecordingTransport:
    def __init__(self, contents: list[str] | None = None):
        self.contents = list(contents or ["{}"])
        self.calls: list[dict[str, Any]] = []

    def post_json(self, url, payload, headers):
        self.calls.append(
            {
                "url": url,
                "payload": json.loads(json.dumps(payload)),
                "headers": dict(headers),
            }
        )
        content = self.contents.pop(0)
        return {"choices": [{"message": {"content": content}}]}


def _config(**changes: Any) -> ProviderConfig:
    values: dict[str, Any] = {
        "base_url": "https://model.internal.example/v1",
        "model": "offline-test-model",
    }
    values.update(changes)
    return ProviderConfig(**values)


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("ftp://model.example/v1", "BASE_URL_INVALID"),
        ("https://user:secret@model.example/v1", "BASE_URL_INVALID"),
        ("https://model.example/v1?secret=x", "BASE_URL_INVALID"),
        ("https://model.example/v1/../v1", "BASE_URL_INVALID"),
        ("https://metadata.google.internal/v1", "HOST_BLOCKED"),
        ("https://169.254.169.254/v1", "ADDRESS_BLOCKED"),
        ("https://127.0.0.1/v1", "LOOPBACK_DISABLED"),
        ("https://model.example/api", "BASE_URL_INVALID"),
    ],
)
def test_base_url_policy_fails_closed(url, code):
    with pytest.raises(ProviderPolicyError) as captured:
        validate_model_base_url(url)
    assert captured.value.code == code


def test_lab_network_overrides_are_independent_and_explicit():
    with pytest.raises(ProviderPolicyError) as captured:
        _config(base_url="http://127.0.0.1:8080/v1")
    assert captured.value.code == "INSECURE_HTTP_DISABLED"

    allowed = _config(
        base_url="http://127.0.0.1:8080/v1",
        allow_insecure_http=True,
        allow_loopback=True,
    )
    assert allowed.base_url == "http://127.0.0.1:8080/v1"
    assert allowed.tls_verify is True

    with pytest.raises(ProviderPolicyError) as captured:
        _config(tls_verify=False)
    assert captured.value.code == "TLS_VERIFY_REQUIRED"
    assert _config(tls_verify=False, allow_insecure_tls=True).tls_verify is False


def test_custom_ca_must_be_an_existing_absolute_file(tmp_path):
    with pytest.raises(ProviderPolicyError) as captured:
        _config(ca_bundle="relative-ca.pem")
    assert captured.value.code == "CA_BUNDLE_INVALID"

    bundle = tmp_path / "internal-ca.pem"
    bundle.write_text("fixture only", encoding="utf-8")
    assert _config(ca_bundle=str(bundle)).ca_bundle == str(bundle)


def test_authentication_secret_is_never_in_repr_or_policy_errors():
    secret = "Bearer super-secret-token"
    config = _config(auth_value=secret)
    assert secret not in repr(config)

    with pytest.raises(ProviderPolicyError) as captured:
        _config(auth_value=secret + "\nInjected: yes")
    assert captured.value.code == "AUTH_VALUE_INVALID"
    assert secret not in str(captured.value)

    with pytest.raises(ProviderPolicyError):
        _config(auth_header="Host")


def test_generate_uses_schema_or_grammar_without_tools_or_functions():
    schema = {"type": "object", "additionalProperties": False}
    schema_transport = RecordingTransport(['{"ok":true}'])
    schema_provider = OpenAICompatibleProvider(
        _config(auth_value="Bearer test"),
        capabilities=ProviderCapabilities(json_schema=True),
        transport=schema_transport,
    )
    assert schema_provider.generate(
        [{"role": "user", "content": "build"}],
        schema=schema,
        grammar='root ::= "{}"',
    ) == '{"ok":true}'
    schema_payload = schema_transport.calls[0]["payload"]
    assert schema_payload["response_format"]["json_schema"]["strict"] is True
    assert "grammar" not in schema_payload
    assert "tools" not in schema_payload
    assert "functions" not in schema_payload
    assert schema_transport.calls[0]["headers"]["Authorization"] == "Bearer test"

    grammar_transport = RecordingTransport()
    grammar_provider = OpenAICompatibleProvider(
        _config(),
        capabilities=ProviderCapabilities(grammar=True),
        transport=grammar_transport,
    )
    grammar_provider.generate(
        [{"role": "user", "content": "build"}],
        schema=schema,
        grammar='root ::= "{}"',
    )
    grammar_payload = grammar_transport.calls[0]["payload"]
    assert grammar_payload["grammar"] == 'root ::= "{}"'
    assert "response_format" not in grammar_payload


def test_generation_fails_closed_without_a_proven_constraint():
    schema = {"type": "object", "additionalProperties": False}
    provider = OpenAICompatibleProvider(
        _config(),
        transport=RecordingTransport(),
    )
    with pytest.raises(ProviderPolicyError) as captured:
        provider.generate(
            [{"role": "user", "content": "build"}],
            schema=schema,
            grammar='root ::= "{}"',
        )
    assert captured.value.code == "CONSTRAINT_UNAVAILABLE"

    lab_transport = RecordingTransport()
    lab_provider = OpenAICompatibleProvider(
        _config(allow_unconstrained_json=True),
        transport=lab_transport,
    )
    lab_provider.generate(
        [{"role": "user", "content": "build"}],
        schema=schema,
        grammar='root ::= "{}"',
    )
    assert "response_format" not in lab_transport.calls[0]["payload"]
    assert "grammar" not in lab_transport.calls[0]["payload"]


def test_probe_verifies_constraint_output_instead_of_trusting_http_success():
    schema_transport = RecordingTransport(["{}"])
    schema_probe = OpenAICompatibleProvider(
        _config(),
        transport=schema_transport,
    ).probe()
    assert schema_probe.reachable is True
    assert schema_probe.json_schema is True
    assert schema_probe.grammar is False
    assert len(schema_transport.calls) == 1

    grammar_transport = RecordingTransport(
        ["constraint was ignored", " { } "]
    )
    grammar_probe = OpenAICompatibleProvider(
        _config(),
        transport=grammar_transport,
    ).probe()
    assert grammar_probe.reachable is True
    assert grammar_probe.json_schema is False
    assert grammar_probe.grammar is True
    assert "CONSTRAINT_IGNORED" in grammar_probe.detail


def test_message_and_response_shapes_are_strict():
    schema = {"type": "object", "additionalProperties": False}
    provider = OpenAICompatibleProvider(
        _config(),
        capabilities=ProviderCapabilities(json_schema=True),
        transport=RecordingTransport(),
    )
    with pytest.raises(ProviderPolicyError) as captured:
        provider.generate(
            [{"role": "tool", "content": "not allowed"}],
            schema=schema,
        )
    assert captured.value.code == "MESSAGES_INVALID"

    with pytest.raises(ProviderPolicyError) as captured:
        provider.generate(
            [{"role": "user", "content": "x" * (256 * 1024 + 1)}],
            schema=schema,
        )
    assert captured.value.code == "MESSAGES_TOO_LARGE"

    class BadTransport:
        def post_json(self, url, payload, headers):
            return {"choices": []}

    with pytest.raises(ProviderResponseError) as captured:
        OpenAICompatibleProvider(
            _config(),
            capabilities=ProviderCapabilities(json_schema=True),
            transport=BadTransport(),
        ).generate(
            [{"role": "user", "content": "x"}],
            schema=schema,
        )
    assert captured.value.code == "RESPONSE_SHAPE_INVALID"


class _FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int) -> bytes:
        return self.body[:size]


class _FakeOpener:
    def __init__(self, body: bytes):
        self.body = body

    def open(self, request, timeout):
        return _FakeResponse(self.body)


class _RaisingOpener:
    def __init__(self, error: Exception):
        self.error = error

    def open(self, request, timeout):
        raise self.error


def test_stdlib_transport_denies_oversized_requests_before_network(
    monkeypatch,
):
    config = _config(max_request_bytes=1024)
    transport = StdlibJSONTransport(config)
    touched_network = False

    def unexpected_dns(*_args, **_kwargs):
        nonlocal touched_network
        touched_network = True
        return []

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_dns)
    with pytest.raises(ProviderPolicyError) as captured:
        transport.post_json(
            "https://model.internal.example/v1/chat/completions",
            {"content": "x" * 2048},
            {},
        )
    assert captured.value.code == "REQUEST_TOO_LARGE"
    assert touched_network is False


def test_stdlib_transport_checks_dns_and_response_size(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.20.30.40", 443),
            )
        ],
    )
    body = b"x" * 1025
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *_handlers: _FakeOpener(body),
    )
    transport = StdlibJSONTransport(_config(max_response_bytes=1024))
    with pytest.raises(ProviderResponseError) as captured:
        transport.post_json(
            "https://model.internal.example/v1/chat/completions",
            {"model": "x"},
            {},
        )
    assert captured.value.code == "RESPONSE_TOO_LARGE"


def test_stdlib_transport_blocks_prohibited_dns_results(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("169.254.169.254", 443),
            )
        ],
    )
    with pytest.raises(ProviderPolicyError) as captured:
        StdlibJSONTransport(_config()).post_json(
            "https://model.internal.example/v1/chat/completions",
            {"model": "x"},
            {},
        )
    assert captured.value.code == "ADDRESS_BLOCKED"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("slow provider included a private detail"),
        urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate included a private detail")
        ),
    ],
)
def test_stdlib_transport_sanitizes_timeout_and_certificate_errors(
    monkeypatch,
    error,
):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.20.30.40", 443),
            )
        ],
    )
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *_handlers: _RaisingOpener(error),
    )
    with pytest.raises(ProviderError) as captured:
        StdlibJSONTransport(_config()).post_json(
            "https://model.internal.example/v1/chat/completions",
            {"model": "x"},
            {},
        )
    assert captured.value.code == "TRANSPORT_FAILED"
    assert "private detail" not in str(captured.value)


def test_stdlib_transport_rejects_non_json_response(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.20.30.40", 443),
            )
        ],
    )
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *_handlers: _FakeOpener(b"<html>not json</html>"),
    )
    with pytest.raises(ProviderResponseError) as captured:
        StdlibJSONTransport(_config()).post_json(
            "https://model.internal.example/v1/chat/completions",
            {"model": "x"},
            {},
        )
    assert captured.value.code == "RESPONSE_JSON_INVALID"
