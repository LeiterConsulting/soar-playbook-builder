"""SOAR REST helpers for connector actions and REST handler (sidecar) contexts.

REST handlers run under Django and **cannot** call ``phantom.app.rest`` on many SOAR
builds. For sidecar import, loop back to ``/rest/...`` using the incoming request
auth (Splunk-documented ``ph-auth-token`` pattern, session cookies, or Basic auth).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_RETRY_MARKERS = (
    "ALLOWED_HOSTS",
    "Invalid HTTP_HOST",
    "Connection refused",
    "Errno 61",
    "Errno 111",
    "Network is unreachable",
    "timed out",
    "Name or service not known",
    "HTTP 401",
    "HTTP 404",
    "not found rest",
    "session token",
    "Authentication failed",
    "CERTIFICATE_VERIFY_FAILED",
    "certificate verify failed",
    "IP address mismatch",
    "Hostname mismatch",
)
MAX_SOAR_REST_RESPONSE_BYTES = 4 * 1024 * 1024
ALLOWED_SOAR_REST_SCHEMES = frozenset({"http", "https"})
ALLOWED_SOAR_REST_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE"}
)


def _safe_header_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or any(ord(char) < 32 or ord(char) == 127 for char in text):
        return None
    return text


def _validate_rest_base(base: str) -> str:
    normalized = str(base or "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if (
        parsed.scheme.lower() not in ALLOWED_SOAR_REST_SCHEMES
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("SOAR REST base URL must be an HTTP(S) origin/path")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("SOAR REST base URL has an invalid port") from exc
    return normalized


def _normalize_rest_path(path: str) -> str:
    normalized = (path or "").strip().lstrip("/")
    if normalized.startswith("rest/"):
        normalized = normalized[5:]
    return normalized.lstrip("/")


def _join_rest_url(base: str, path: str) -> str:
    """Join REST base + endpoint without duplicating ``/rest/``."""
    normalized = _normalize_rest_path(path)
    root = _validate_rest_base(base)
    if root.endswith("/rest"):
        return f"{root}/{normalized}"
    return f"{root}/rest/{normalized}"


def _load_phantom_modules() -> list[Any]:
    mods = []
    for name in ("phantom.app", "phantom.rules"):
        try:
            mods.append(__import__(name, fromlist=["phantom"]))
        except ImportError:
            continue
    return mods


def _find_phantom_rest() -> Any | None:
    for mod in _load_phantom_modules():
        rest_fn = getattr(mod, "rest", None)
        if callable(rest_fn):
            return rest_fn
    return None


def _platform_rest_base_url() -> str | None:
    try:
        from phantom_common.install_info import get_rest_base_url

        base = str(get_rest_base_url()).rstrip("/")
        return base or None
    except Exception:  # noqa: BLE001
        return None


def _parse_host_port(request: Any) -> tuple[str, str]:
    """Return (hostname, port) from the incoming Django request."""
    host = ""
    if hasattr(request, "get_host"):
        try:
            host = request.get_host()
        except Exception:  # noqa: BLE001
            host = ""
    if not host and hasattr(request, "META"):
        host = request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME") or ""
    port = str(request.META.get("SERVER_PORT", "")) if hasattr(request, "META") else ""
    if host and ":" in host:
        hostname, _, port_part = host.rpartition(":")
        return hostname, port_part or port or ("443" if _request_is_secure(request) else "80")
    return host or "127.0.0.1", port or ("443" if _request_is_secure(request) else "80")


def _request_is_secure(request: Any) -> bool:
    if hasattr(request, "is_secure") and callable(request.is_secure):
        try:
            return bool(request.is_secure())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(request, "META"):
        return request.META.get("wsgi.url_scheme") == "https"
    return True


def _client_host_header(request: Any) -> str:
    if hasattr(request, "get_host"):
        try:
            host = request.get_host()
            if host:
                return host
        except Exception:  # noqa: BLE001
            pass
    hostname, port = _parse_host_port(request)
    port_suffix = f":{port}" if port and port not in ("80", "443") else ""
    return f"{hostname}{port_suffix}"


def _extract_ph_auth_token(request: Any) -> str | None:
    asset_token = getattr(request, "_soar_rest_token", None)
    if asset_token:
        return str(asset_token).strip()

    meta = getattr(request, "META", None) or {}
    for key in ("HTTP_PH_AUTH_TOKEN", "HTTP_X_PH_AUTH_TOKEN", "HTTP_X_SOAR_TOKEN"):
        raw = meta.get(key)
        if raw:
            return str(raw).strip()
    cookies = getattr(request, "COOKIES", None) or {}
    for name in ("ph-auth-token", "ph_auth_token", "phauthtoken"):
        raw = cookies.get(name)
        if raw:
            return str(raw).strip()
    return None


def _django_rest_targets(request: Any) -> list[tuple[str, str | None]]:
    """Return (url_base, Host header override) pairs for internal REST loopback.

    Prefer platform internal base URL and client-matching Host (preserves UI session)
    before loopback Host spoofing for Django ALLOWED_HOSTS.
    """
    hostname, port = _parse_host_port(request)
    scheme = "https" if _request_is_secure(request) else "http"
    port_suffix = f":{port}" if port and port not in ("80", "443") else ""
    client_host = _client_host_header(request)
    server_name = ""
    if hasattr(request, "META"):
        server_name = str(request.META.get("SERVER_NAME") or "").strip()

    connect_hosts: list[str] = []
    platform_base = _platform_rest_base_url()
    if platform_base:
        try:
            connect_hosts.append(_validate_rest_base(platform_base))
        except ValueError:
            pass

    for candidate in (hostname, server_name, "127.0.0.1", "localhost"):
        if not candidate:
            continue
        try:
            candidate_base = _validate_rest_base(
                f"{scheme}://{candidate}{port_suffix}"
            )
        except ValueError:
            continue
        if candidate_base not in connect_hosts:
            connect_hosts.append(candidate_base)

    host_headers: list[str | None] = [client_host, None]
    for candidate in ("127.0.0.1", "localhost", server_name, hostname):
        if not candidate:
            continue
        with_port = f"{candidate}{port_suffix}" if port_suffix else candidate
        for hdr in (with_port, candidate):
            if hdr and hdr not in host_headers:
                host_headers.append(hdr)

    targets: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for base in connect_hosts:
        normalized_base = base.rstrip("/")
        for hdr in host_headers:
            key = (normalized_base, hdr)
            if key in seen:
                continue
            seen.add(key)
            targets.append(key)
    return targets


def build_phantom_rest_url(path: str, *, request: Any | None = None, target_index: int = 0) -> str:
    """Build a SOAR REST URL for ``import_playbook``, ``playbook``, etc."""
    normalized = _normalize_rest_path(path)

    if request is not None:
        targets = _django_rest_targets(request)
        base, _ = targets[min(target_index, len(targets) - 1)]
        return _join_rest_url(base, normalized)

    platform_base = _platform_rest_base_url()
    if platform_base:
        try:
            return _join_rest_url(platform_base, normalized)
        except ValueError:
            pass

    for mod in _load_phantom_modules():
        fn = getattr(mod, "build_phantom_rest_url", None)
        if callable(fn):
            return fn(normalized)

    for mod in _load_phantom_modules():
        base_fn = getattr(mod, "get_rest_base_url", None)
        if callable(base_fn):
            base = str(base_fn()).rstrip("/")
            return f"{base}/{normalized.lstrip('/')}"

    return f"/rest/{normalized.lstrip('/')}"


def _request_auth_headers(request: Any) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not hasattr(request, "META"):
        return headers

    token = _extract_ph_auth_token(request)
    safe_token = _safe_header_value(token)
    if safe_token:
        headers["ph-auth-token"] = safe_token

    auth = _safe_header_value(request.META.get("HTTP_AUTHORIZATION"))
    if auth:
        headers["Authorization"] = auth

    csrf = _safe_header_value(request.META.get("HTTP_X_CSRFTOKEN"))
    if csrf:
        headers["X-CSRFToken"] = csrf

    referer = _safe_header_value(request.META.get("HTTP_REFERER"))
    if referer:
        headers["Referer"] = referer

    headers["X-Requested-With"] = "XMLHttpRequest"
    return headers


def _request_cookie_header(request: Any) -> str | None:
    cookies = getattr(request, "COOKIES", None)
    if not cookies:
        return None
    values: list[str] = []
    for key, value in cookies.items():
        safe_key = _safe_header_value(key)
        safe_value = _safe_header_value(value)
        if (
            safe_key
            and safe_value
            and all(char not in safe_key for char in "=;,")
            and all(char not in safe_value for char in ";\r\n")
        ):
            values.append(f"{safe_key}={safe_value}")
    return "; ".join(values) or None


def _should_retry_loopback(error_text: str) -> bool:
    text = error_text or ""
    return any(marker in text for marker in _RETRY_MARKERS)


def _single_django_request(
    url: str,
    host_header: str | None,
    request: Any,
    method: str,
    body: dict[str, Any] | None,
    *,
    params: dict[str, Any] | None,
    timeout: int,
) -> tuple[bool, Any]:
    if params:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{qs}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update(_request_auth_headers(request))
    safe_host_header = _safe_header_value(host_header)
    if safe_host_header:
        headers["Host"] = safe_host_header

    cookie = _request_cookie_header(request)
    if cookie:
        headers["Cookie"] = cookie

    data = None
    method_upper = method.upper()
    if method_upper not in ALLOWED_SOAR_REST_METHODS:
        return False, "SOAR REST method is not allowed"
    if body is not None and method_upper != "GET":
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method_upper)
    cfg = getattr(request, "_pb_config", None) or {}
    allow_insecure_tls = str(
        cfg.get("soar_loopback_allow_insecure_tls") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    ca_bundle = str(cfg.get("soar_loopback_ca_bundle") or "").strip() or None
    try:
        if allow_insecure_tls:
            ctx = ssl._create_unverified_context()  # noqa: SLF001  # nosec B323
        else:
            ctx = ssl.create_default_context(cafile=ca_bundle)
        # URL was constrained to an HTTP(S) origin by _validate_rest_base.
        with urllib.request.urlopen(  # nosec B310
            req,
            context=ctx,
            timeout=timeout,
        ) as resp:
            body_bytes = resp.read(MAX_SOAR_REST_RESPONSE_BYTES + 1)
            if len(body_bytes) > MAX_SOAR_REST_RESPONSE_BYTES:
                return False, "SOAR REST response exceeded the byte limit"
            raw = body_bytes.decode("utf-8", errors="replace")
            if not raw.strip():
                return True, {}
            try:
                return True, json.loads(raw)
            except json.JSONDecodeError:
                return True, raw
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return False, f"HTTP {exc.code}: {detail}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def django_request_rest(
    request: Any,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 45,
) -> tuple[bool, Any, list[str]]:
    """Call SOAR ``/rest/...`` from a REST handler using the caller's auth."""
    normalized = _normalize_rest_path(path)

    attempts_log: list[str] = []
    last_error = "SOAR REST loopback failed"
    targets = _django_rest_targets(request)

    for base, host_header in targets:
        url = _join_rest_url(base, normalized)
        ok, result = _single_django_request(
            url, host_header, request, method, body, params=params, timeout=timeout,
        )
        host_label = host_header if host_header is not None else "(default)"
        attempts_log.append(f"loopback {url} Host={host_label!r} -> {ok}")
        if ok:
            return True, result, attempts_log
        last_error = str(result)
        if not _should_retry_loopback(last_error):
            return False, result, attempts_log

    return False, last_error, attempts_log


def phantom_rest_call(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    params: dict[str, Any] | None = None,
    request: Any | None = None,
    timeout: int = 45,
) -> tuple[bool, Any]:
    """SOAR REST call — REST handler (``request`` set) or connector (``phantom.rest``)."""
    if request is not None:
        ok, result, _log = django_request_rest(
            request, method, path, body, params=params, timeout=timeout,
        )
        return ok, result

    rest_fn = _find_phantom_rest()
    if rest_fn is None:
        return False, (
            "No SOAR REST API available (phantom.rest missing and no Django request). "
            "Import must run from the sidecar REST handler."
        )

    url = build_phantom_rest_url(path)
    method_upper = method.upper()

    if method_upper == "GET":
        try:
            return _coerce_rest_result(rest_fn(url, params=params or {"page_size": 500}))
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    payload = json.dumps(body or {})
    attempts: list[dict[str, Any]] = [
        {"method": method, "data": payload, "headers": {"Content-Type": "application/json"}},
        {"method": method_upper, "data": payload, "headers": {"Content-Type": "application/json"}},
        {"method": method, "body": body or {}},
        {"method": method_upper, "body": body or {}},
    ]
    last_error = "phantom.rest POST failed"
    for kwargs in attempts:
        try:
            return _coerce_rest_result(rest_fn(url, **kwargs))
        except TypeError as exc:
            last_error = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
    return False, last_error


def _coerce_rest_result(result: Any) -> tuple[bool, Any]:
    if isinstance(result, tuple):
        if len(result) >= 3:
            return bool(result[0]), result[2]
        if len(result) == 2:
            ok, payload = result[0], result[1]
            if isinstance(ok, bool):
                return ok, payload
            return bool(payload), ok
    return bool(result), result
