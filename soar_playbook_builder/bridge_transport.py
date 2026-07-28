"""Bounded, no-redirect transport for the optional MCP bridge."""

from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import urllib.parse
import urllib.request
from typing import Any

MAX_BRIDGE_REQUEST_BYTES = 512 * 1024
MAX_BRIDGE_RESPONSE_BYTES = 1024 * 1024
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.aws.internal",
        "instance-data",
    }
)


class BridgePolicyError(ValueError):
    """The configured bridge or requested payload violates local policy."""


class BridgeResponseTooLargeError(ValueError):
    """The bridge response exceeded the configured byte limit."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _validate_ip(address: str) -> None:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as exc:
        raise BridgePolicyError("MCP bridge resolved to an invalid address") from exc
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_unspecified or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise BridgePolicyError(f"bridge address is not permitted: {ip}")


def validate_bridge_base_url(
    value: str,
    *,
    allow_insecure_http: bool = False,
) -> str:
    """Return a normalized bridge base URL or raise a policy error."""
    supplied = str(value or "")
    if supplied != supplied.strip():
        raise BridgePolicyError("MCP bridge URL contains surrounding whitespace")
    raw = supplied.rstrip("/")
    if not raw:
        raise BridgePolicyError("MCP bridge URL is not configured")
    if any(ord(char) < 33 for char in raw):
        raise BridgePolicyError("MCP bridge URL contains whitespace or control characters")

    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise BridgePolicyError("MCP bridge URL must use https")
    if parsed.scheme == "http" and not allow_insecure_http:
        raise BridgePolicyError(
            "Plain HTTP is disabled. Use HTTPS or explicitly enable lab-only insecure HTTP."
        )
    if not parsed.hostname:
        raise BridgePolicyError("MCP bridge URL must include a hostname")
    if parsed.username or parsed.password:
        raise BridgePolicyError("Credentials are not permitted in the MCP bridge URL")
    if parsed.query or parsed.fragment:
        raise BridgePolicyError("Query strings and fragments are not permitted in the MCP bridge URL")
    if parsed.hostname.lower().rstrip(".") in _BLOCKED_HOSTNAMES:
        raise BridgePolicyError("Cloud metadata endpoints are not permitted")
    if "%" in parsed.hostname:
        raise BridgePolicyError("Scoped IPv6 addresses are not permitted")
    try:
        port = parsed.port
    except ValueError as exc:
        raise BridgePolicyError("MCP bridge URL contains an invalid port") from exc
    if port is not None and port < 1:
        raise BridgePolicyError("MCP bridge URL contains an invalid port")
    path_segments = parsed.path.split("/")
    if "." in path_segments or ".." in path_segments:
        raise BridgePolicyError("Relative path segments are not permitted in the MCP bridge URL")
    if not parsed.path.rstrip("/").endswith("/agent"):
        raise BridgePolicyError("MCP bridge URL path must end with /agent")

    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        _validate_ip(parsed.hostname)
    return raw


def _resolve_and_validate_host(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise BridgePolicyError("MCP bridge hostname could not be resolved") from exc
    if not addresses:
        raise BridgePolicyError("MCP bridge hostname resolved to no addresses")
    for info in addresses:
        _validate_ip(info[4][0])


def _bridge_endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def bridge_request_text(
    base_url: str,
    suffix: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
    allow_insecure_http: bool = False,
    max_response_bytes: int = MAX_BRIDGE_RESPONSE_BYTES,
) -> str:
    """Call a bridge endpoint with verified TLS, no redirects, and byte limits."""
    normalized = validate_bridge_base_url(
        base_url,
        allow_insecure_http=allow_insecure_http,
    )
    url = _bridge_endpoint(normalized, suffix)
    _resolve_and_validate_host(url)

    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_BRIDGE_REQUEST_BYTES:
            raise BridgePolicyError("MCP bridge request exceeds the byte limit")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method.upper(),
    )
    handlers: list[Any] = [
        urllib.request.ProxyHandler({}),
        _NoRedirectHandler(),
    ]
    if urllib.parse.urlsplit(url).scheme == "https":
        handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    opener = urllib.request.build_opener(*handlers)
    with opener.open(request, timeout=timeout) as response:
        body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise BridgeResponseTooLargeError("MCP bridge response exceeds the byte limit")
    return body.decode("utf-8", errors="replace")


def bridge_request_json(
    base_url: str,
    suffix: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
    allow_insecure_http: bool = False,
    max_response_bytes: int = MAX_BRIDGE_RESPONSE_BYTES,
) -> Any:
    """Call a bridge endpoint and parse its bounded JSON response."""
    text = bridge_request_text(
        base_url,
        suffix,
        method=method,
        payload=payload,
        timeout=timeout,
        allow_insecure_http=allow_insecure_http,
        max_response_bytes=max_response_bytes,
    )
    return json.loads(text)
