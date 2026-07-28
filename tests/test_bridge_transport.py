"""Tests for MCP bridge URL and transport policy."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from bridge_transport import (  # noqa: E402
    BridgePolicyError,
    BridgeResponseTooLargeError,
    bridge_request_json,
    validate_bridge_base_url,
)


def _resolved(address: str = "10.20.30.40"):
    return [(2, 1, 6, "", (address, 443))]


def test_bridge_url_requires_https_by_default():
    with pytest.raises(BridgePolicyError, match="Plain HTTP"):
        validate_bridge_base_url("http://10.20.30.40:8003/agent")

    assert (
        validate_bridge_base_url(
            "http://10.20.30.40:8003/agent",
            allow_insecure_http=True,
        )
        == "http://10.20.30.40:8003/agent"
    )


@pytest.mark.parametrize(
    "url",
    (
        "file:///tmp/agent",
        "https://user:pass@bridge.internal/agent",
        "https://bridge.internal/agent?next=http://metadata/",
        "https://bridge.internal/agent#fragment",
        "https://169.254.169.254/agent",
        "https://metadata.google.internal/agent",
        "https://bridge.internal/not-agent",
        "https://bridge.internal/base/../agent",
        "https://bridge.internal:0/agent",
        "https://bridge.internal/agent\n",
    ),
)
def test_bridge_url_rejects_unsafe_shapes(url: str):
    with pytest.raises(BridgePolicyError):
        validate_bridge_base_url(url)


def test_bridge_request_rejects_dns_resolution_to_link_local():
    with patch("bridge_transport.socket.getaddrinfo", return_value=_resolved("169.254.1.2")):
        with pytest.raises(BridgePolicyError, match="not permitted"):
            bridge_request_json("https://bridge.internal/agent", "health")


def test_bridge_request_disables_redirects_and_parses_bounded_json():
    response = MagicMock()
    response.read.return_value = json.dumps({"status": "ok"}).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    opener = MagicMock()
    opener.open.return_value = response

    with patch("bridge_transport.socket.getaddrinfo", return_value=_resolved()):
        with patch("bridge_transport.urllib.request.build_opener", return_value=opener) as build:
            result = bridge_request_json("https://bridge.internal/agent", "health")

    assert result == {"status": "ok"}
    assert any(
        handler.__class__.__name__ == "_NoRedirectHandler"
        for handler in build.call_args.args
    )


def test_bridge_request_rejects_oversized_response():
    response = MagicMock()
    response.read.return_value = b"x" * 11
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    opener = MagicMock()
    opener.open.return_value = response

    with patch("bridge_transport.socket.getaddrinfo", return_value=_resolved()):
        with patch("bridge_transport.urllib.request.build_opener", return_value=opener):
            with pytest.raises(BridgeResponseTooLargeError):
                bridge_request_json(
                    "https://bridge.internal/agent",
                    "health",
                    max_response_bytes=10,
                )


def test_redirect_is_not_followed():
    redirect = urllib.error.HTTPError(
        "https://bridge.internal/agent/health",
        302,
        "Found",
        {"Location": "http://169.254.169.254/latest"},
        io.BytesIO(b""),
    )
    opener = MagicMock()
    opener.open.side_effect = redirect

    with patch("bridge_transport.socket.getaddrinfo", return_value=_resolved()):
        with patch("bridge_transport.urllib.request.build_opener", return_value=opener):
            with pytest.raises(urllib.error.HTTPError) as exc:
                bridge_request_json("https://bridge.internal/agent", "health")
    assert exc.value.code == 302
