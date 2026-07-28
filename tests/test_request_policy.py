"""Tests for the REST-handler HTTP method allowlist."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from request_policy import (  # noqa: E402
    RequestPolicyError,
    chat_get_is_allowed,
    parse_json_post,
    route_method_is_allowed,
)


class _Request:
    method = "POST"
    content_type = "application/json"

    def __init__(self, body: object, *, origin: str = "https://soar.example"):
        self.body = json.dumps(body).encode()
        self.META = {
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(self.body)),
            "HTTP_HOST": "soar.example",
            "HTTP_ORIGIN": origin,
        }

    def build_absolute_uri(self, _path: str) -> str:
        return "https://soar.example/"

    def get_host(self) -> str:
        return "soar.example"

    def is_secure(self) -> bool:
        return True


def test_chat_get_allows_explicit_read_only_actions():
    for action in (
        "list_patterns",
        "list_ir_templates",
        "trusted_retrieve",
        "environment_check",
        "list_cases",
        "troubleshoot",
    ):
        assert chat_get_is_allowed({"action": action}) is True


def test_chat_get_rejects_mutations_and_messages():
    for query in (
        {"action": "import_draft"},
        {"action": "run_playbook"},
        {"action": "scaffold"},
        {"action": "rebuild_capability_index"},
        {"message": "build a playbook"},
        {"poll": "1"},
        {},
    ):
        assert chat_get_is_allowed(query) is False


def test_route_method_matrix_is_deny_by_default():
    assert route_method_is_allowed("chat", "GET") is True
    assert route_method_is_allowed("chat", "POST") is True
    assert route_method_is_allowed("poll_playbook", "POST") is True
    assert route_method_is_allowed("poll_playbook", "GET") is False
    assert route_method_is_allowed("proxy_chat", "GET") is False
    assert route_method_is_allowed("unknown", "GET") is False


def test_parse_json_post_accepts_same_origin_object():
    assert parse_json_post(_Request({"action": "chat"})) == {"action": "chat"}


def test_parse_json_post_rejects_cross_origin():
    with pytest.raises(RequestPolicyError) as exc:
        parse_json_post(_Request({"action": "chat"}, origin="https://evil.example"))
    assert exc.value.status == 403
    assert exc.value.code == "CROSS_ORIGIN_REQUEST_REJECTED"


def test_parse_json_post_rejects_wrong_content_type():
    request = _Request({"action": "chat"})
    request.content_type = "text/plain"
    request.META["CONTENT_TYPE"] = "text/plain"
    with pytest.raises(RequestPolicyError) as exc:
        parse_json_post(request)
    assert exc.value.status == 415


def test_parse_json_post_rejects_oversized_and_non_object_bodies():
    request = _Request({"source": "x" * 20})
    with pytest.raises(RequestPolicyError) as exc:
        parse_json_post(request, max_bytes=10)
    assert exc.value.status == 413

    non_object = _Request(["chat"])
    with pytest.raises(RequestPolicyError) as exc:
        parse_json_post(non_object)
    assert exc.value.code == "JSON_OBJECT_REQUIRED"


def test_parse_json_post_rejects_invalid_json():
    request = _Request({})
    request.body = b"{bad"
    request.META["CONTENT_LENGTH"] = str(len(request.body))
    with pytest.raises(RequestPolicyError) as exc:
        parse_json_post(request)
    assert exc.value.code == "INVALID_JSON"
