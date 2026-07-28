"""HTTP method policy for the sidecar REST handler."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

MAX_JSON_REQUEST_BYTES = 1024 * 1024

READ_ONLY_CHAT_ACTIONS = frozenset(
    {
        "bridge_status",
        "coach_suggest",
        "environment_check",
        "get_lesson",
        "investigation_context",
        "links",
        "list_cases",
        "list_lessons",
        "list_patterns",
        "list_ir_templates",
        "list_troubleshooting",
        "steps",
        "template_manifest",
        "trusted_retrieve",
        "troubleshoot",
    }
)
ROUTE_METHODS: dict[str, frozenset[str]] = {
    "chat": frozenset({"GET", "POST"}),
    "widget": frozenset({"GET"}),
    "list_lessons": frozenset({"GET"}),
    "poll_playbook": frozenset({"POST"}),
    "proxy_chat": frozenset({"POST"}),
    "es_link": frozenset({"GET"}),
    "splunk_link": frozenset({"GET"}),
}


class RequestPolicyError(ValueError):
    """A request failed a public REST boundary policy check."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def payload(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "error": self.message,
        }


def chat_get_is_allowed(query: Mapping[str, Any]) -> bool:
    """Return true only for explicitly read-only chat actions."""
    action = str(query.get("action") or "").strip().lower()
    return bool(action and action in READ_ONLY_CHAT_ACTIONS)


def route_method_is_allowed(route: str, method: str) -> bool:
    """Return true only when a known handler route permits the HTTP method."""
    allowed = ROUTE_METHODS.get(str(route))
    return bool(allowed and str(method).upper() in allowed)


def _request_origin(request: Any) -> str:
    try:
        absolute = request.build_absolute_uri("/")
    except Exception:  # noqa: BLE001
        host = str(getattr(request, "META", {}).get("HTTP_HOST") or request.get_host())
        scheme = "https" if request.is_secure() else "http"
        absolute = f"{scheme}://{host}/"
    parsed = urlsplit(absolute)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _validate_browser_origin(request: Any) -> None:
    meta = getattr(request, "META", {}) or {}
    supplied = str(meta.get("HTTP_ORIGIN") or "").strip()
    if not supplied:
        referer = str(meta.get("HTTP_REFERER") or "").strip()
        if referer:
            parsed_referer = urlsplit(referer)
            supplied = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
    if not supplied:
        return
    parsed = urlsplit(supplied)
    supplied_origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    if not parsed.scheme or not parsed.netloc or supplied_origin != _request_origin(request):
        raise RequestPolicyError(
            403,
            "CROSS_ORIGIN_REQUEST_REJECTED",
            "Cross-origin requests are not permitted.",
        )


def parse_json_post(
    request: Any,
    *,
    max_bytes: int = MAX_JSON_REQUEST_BYTES,
) -> dict[str, Any]:
    """Validate and parse a bounded, same-origin JSON POST object."""
    if str(getattr(request, "method", "")).upper() != "POST":
        raise RequestPolicyError(
            405,
            "METHOD_NOT_ALLOWED",
            "This operation requires a JSON POST request.",
        )

    meta = getattr(request, "META", {}) or {}
    content_type = str(
        getattr(request, "content_type", "")
        or meta.get("CONTENT_TYPE")
        or ""
    ).split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise RequestPolicyError(
            415,
            "JSON_CONTENT_TYPE_REQUIRED",
            "Content-Type must be application/json.",
        )

    content_length = str(meta.get("CONTENT_LENGTH") or "").strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise RequestPolicyError(
                400,
                "INVALID_CONTENT_LENGTH",
                "Content-Length is invalid.",
            ) from exc
        if declared_length < 0:
            raise RequestPolicyError(
                400,
                "INVALID_CONTENT_LENGTH",
                "Content-Length is invalid.",
            )
        if declared_length > max_bytes:
            raise RequestPolicyError(
                413,
                "REQUEST_TOO_LARGE",
                "JSON request exceeds the permitted size.",
            )

    raw = getattr(request, "body", b"") or b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > max_bytes:
        raise RequestPolicyError(
            413,
            "REQUEST_TOO_LARGE",
            "JSON request exceeds the permitted size.",
        )

    _validate_browser_origin(request)
    try:
        payload = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RequestPolicyError(
            400,
            "INVALID_JSON",
            "Request body must contain valid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise RequestPolicyError(
            400,
            "JSON_OBJECT_REQUIRED",
            "Request body must be a JSON object.",
        )
    return payload
