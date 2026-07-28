"""Tests for SOAR REST URL helper (offline mocks)."""

import json
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from soar_rest import (  # noqa: E402
    MAX_SOAR_REST_RESPONSE_BYTES,
    build_phantom_rest_url,
    django_request_rest,
    phantom_rest_call,
)


def _inject_module(name: str, mod: ModuleType) -> None:
    sys.modules[name] = mod


def _mock_request():
    req = MagicMock()
    req.get_host.return_value = "10.236.39.108:8443"
    req.is_secure.return_value = True
    req.META = {"SERVER_PORT": "8443", "HTTP_AUTHORIZATION": "Basic abc"}
    req.COOKIES = {"csrftoken": "csrf123", "sessionid": "sess"}
    req._pb_config = {}
    return req


def test_build_url_avoids_double_rest_prefix():
    req = _mock_request()
    with patch("soar_rest._platform_rest_base_url", return_value="https://127.0.0.1:8443/rest"):
        url = build_phantom_rest_url("import_playbook", request=req)
    assert url == "https://127.0.0.1:8443/rest/import_playbook"
    assert "/rest/rest/" not in url


def test_build_url_prefers_client_host():
    req = _mock_request()
    with patch("soar_rest._platform_rest_base_url", return_value=None):
        url = build_phantom_rest_url("import_playbook", request=req)
    assert url == "https://10.236.39.108:8443/rest/import_playbook"


def test_build_url_uses_phantom_rules_when_app_lacks_helper():
    app_mod = ModuleType("phantom.app")
    rules_mod = ModuleType("phantom.rules")
    rules_mod.build_phantom_rest_url = MagicMock(return_value="https://soar/rest/import_playbook")
    _inject_module("phantom.app", app_mod)
    _inject_module("phantom.rules", rules_mod)

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        url = build_phantom_rest_url("import_playbook")
    assert url == "https://soar/rest/import_playbook"


def test_build_url_rejects_non_http_and_credentialed_bases():
    req = _mock_request()
    for unsafe in (
        "file:///etc/passwd",
        "https://user:password@soar.example",
        "https://soar.example/rest?redirect=evil",
    ):
        with patch(
            "soar_rest._platform_rest_base_url",
            return_value=unsafe,
        ):
            url = build_phantom_rest_url("import_playbook", request=req)
        assert url.startswith("https://10.236.39.108:8443/")


def test_build_url_without_request_ignores_unsafe_platform_base():
    rules_mod = ModuleType("phantom.rules")
    rules_mod.build_phantom_rest_url = MagicMock(
        return_value="https://soar/rest/asset"
    )
    _inject_module("phantom.rules", rules_mod)
    with patch(
        "soar_rest._platform_rest_base_url",
        return_value="file:///etc/passwd",
    ):
        assert build_phantom_rest_url("asset") == "https://soar/rest/asset"


def test_django_request_rest_rejects_method_and_header_injection():
    req = _mock_request()
    req.META["HTTP_AUTHORIZATION"] = "Bearer safe\r\nX-Evil: 1"
    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("urllib.request.urlopen") as urlopen:
            ok, message, _ = django_request_rest(
                req,
                "TRACE",
                "asset",
            )
    assert ok is False
    assert "method is not allowed" in message
    urlopen.assert_not_called()


def test_phantom_rest_call_uses_client_host_first():
    req = _mock_request()

    payload = {"status": "success", "id": 99}
    body = json.dumps(payload).encode("utf-8")
    fake_resp = MagicMock()
    fake_resp.read.return_value = body
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("urllib.request.urlopen", return_value=fake_resp) as urlopen:
            ok, data = phantom_rest_call("POST", "import_playbook", {"playbook": "x"}, request=req)

    assert ok is True
    assert data == payload
    called_req = urlopen.call_args[0][0]
    assert called_req.full_url == "https://10.236.39.108:8443/rest/import_playbook"
    assert called_req.get_header("Host") in ("10.236.39.108:8443", None)


def test_django_request_rest_retries_on_session_token_401():
    req = _mock_request()

    payload = {"id": 1}
    success_resp = MagicMock()
    success_resp.read.return_value = json.dumps(payload).encode("utf-8")
    success_resp.__enter__ = MagicMock(return_value=success_resp)
    success_resp.__exit__ = MagicMock(return_value=False)

    auth_err = urllib.error.HTTPError(
        url="https://10.236.39.108:8443/rest/import_playbook",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=MagicMock(
            read=MagicMock(
                return_value=b'{"failed": true, "message": "Authentication failed: Invalid or missing session token"}',
            ),
        ),
    )

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("urllib.request.urlopen", side_effect=[auth_err, success_resp]) as urlopen:
            ok, data, log = django_request_rest(req, "POST", "import_playbook", {"playbook": "x"})

    assert ok is True
    assert data == payload
    assert len(log) == 2
    assert urlopen.call_count == 2


def test_django_request_rest_http_403_not_retried():
    req = _mock_request()

    err = urllib.error.HTTPError(
        url="https://10.236.39.108:8443/rest/import_playbook",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=MagicMock(read=MagicMock(return_value=b"nope")),
    )
    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("urllib.request.urlopen", side_effect=err) as urlopen:
            ok, msg, log = django_request_rest(req, "POST", "import_playbook", {"playbook": "x"})
    assert ok is False
    assert "403" in str(msg)
    assert urlopen.call_count == 1
    assert len(log) == 1


def test_django_request_rest_verifies_tls_by_default():
    req = _mock_request()
    response = MagicMock()
    response.read.return_value = b"{}"
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    context = MagicMock()

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("soar_rest.ssl.create_default_context", return_value=context) as create:
            with patch("urllib.request.urlopen", return_value=response) as urlopen:
                ok, _, _ = django_request_rest(req, "GET", "asset")

    assert ok is True
    create.assert_called_with(cafile=None)
    assert urlopen.call_args.kwargs["context"] is context


def test_django_request_rest_insecure_tls_requires_explicit_config():
    req = _mock_request()
    req._pb_config = {"soar_loopback_allow_insecure_tls": True}
    response = MagicMock()
    response.read.return_value = b"{}"
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    context = MagicMock()

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("soar_rest.ssl._create_unverified_context", return_value=context) as create:
            with patch("urllib.request.urlopen", return_value=response):
                ok, _, _ = django_request_rest(req, "GET", "asset")

    assert ok is True
    create.assert_called_once_with()


def test_django_request_rest_rejects_oversized_response():
    req = _mock_request()
    response = MagicMock()
    response.read.return_value = b"x" * (MAX_SOAR_REST_RESPONSE_BYTES + 1)
    response.__enter__.return_value = response
    response.__exit__.return_value = False

    with patch("soar_rest._platform_rest_base_url", return_value=None):
        with patch("urllib.request.urlopen", return_value=response):
            ok, message, log = django_request_rest(req, "GET", "asset")

    assert ok is False
    assert "byte limit" in message
    assert len(log) == 1
