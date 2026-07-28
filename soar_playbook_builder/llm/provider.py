"""Narrow model-provider interface with a hardened stdlib transport."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

MAX_MODEL_REQUEST_BYTES = 512 * 1024
MAX_MODEL_RESPONSE_BYTES = 1024 * 1024
MAX_MESSAGE_BYTES = 256 * 1024
_HEADER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")
_BLOCKED_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "content-type",
        "cookie",
        "host",
        "proxy-authorization",
        "transfer-encoding",
    }
)
_BLOCKED_HOSTS = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.aws.internal",
        "instance-data",
    }
)


class ProviderError(RuntimeError):
    """Stable provider failure without model response or secret content."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class ProviderPolicyError(ProviderError):
    """Configuration or request violates the local trust policy."""


class ProviderResponseError(ProviderError):
    """Endpoint response shape or size is invalid."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass(frozen=True)
class ProviderCapabilities:
    reachable: bool = False
    json_schema: bool = False
    grammar: bool = False
    detail: str = ""


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    model: str
    auth_header: str = "Authorization"
    auth_value: str = field(default="", repr=False)
    timeout_seconds: float = 60.0
    ca_bundle: str = ""
    tls_verify: bool = True
    allow_insecure_http: bool = False
    allow_insecure_tls: bool = False
    allow_loopback: bool = False
    allow_unconstrained_json: bool = False
    max_request_bytes: int = MAX_MODEL_REQUEST_BYTES
    max_response_bytes: int = MAX_MODEL_RESPONSE_BYTES

    def __post_init__(self) -> None:
        normalized = validate_model_base_url(
            self.base_url,
            allow_insecure_http=self.allow_insecure_http,
            allow_loopback=self.allow_loopback,
        )
        object.__setattr__(self, "base_url", normalized)
        if not isinstance(self.model, str) or not self.model or len(self.model) > 256:
            raise ProviderPolicyError(
                "MODEL_INVALID",
                "model name must contain between 1 and 256 characters",
            )
        if any(ord(char) < 32 for char in self.model):
            raise ProviderPolicyError(
                "MODEL_INVALID",
                "model name contains a control character",
            )
        if not _HEADER_RE.fullmatch(self.auth_header):
            raise ProviderPolicyError(
                "AUTH_HEADER_INVALID",
                "authentication header name is invalid",
            )
        if self.auth_header.casefold() in _BLOCKED_HEADERS:
            raise ProviderPolicyError(
                "AUTH_HEADER_INVALID",
                "authentication header name is not permitted",
            )
        if not 1 <= self.timeout_seconds <= 300:
            raise ProviderPolicyError(
                "TIMEOUT_INVALID",
                "model timeout must be between 1 and 300 seconds",
            )
        if not 1024 <= self.max_request_bytes <= 4 * 1024 * 1024:
            raise ProviderPolicyError(
                "REQUEST_LIMIT_INVALID",
                "model request limit is outside the supported range",
            )
        if not 1024 <= self.max_response_bytes <= 8 * 1024 * 1024:
            raise ProviderPolicyError(
                "RESPONSE_LIMIT_INVALID",
                "model response limit is outside the supported range",
            )
        if not self.tls_verify and not self.allow_insecure_tls:
            raise ProviderPolicyError(
                "TLS_VERIFY_REQUIRED",
                "disabled TLS verification requires its explicit lab override",
            )
        if not isinstance(self.auth_value, str):
            raise ProviderPolicyError(
                "AUTH_VALUE_INVALID",
                "authentication value must be a string",
            )
        if any(ord(char) < 32 or ord(char) == 127 for char in self.auth_value):
            raise ProviderPolicyError(
                "AUTH_VALUE_INVALID",
                "authentication value contains a control character",
            )
        if self.ca_bundle:
            path = Path(self.ca_bundle)
            if not path.is_absolute() or not path.is_file():
                raise ProviderPolicyError(
                    "CA_BUNDLE_INVALID",
                    "custom CA bundle must be an existing absolute file",
                )


def _validate_address(address: str, *, allow_loopback: bool) -> None:
    try:
        parsed: ipaddress.IPv4Address | ipaddress.IPv6Address = (
            ipaddress.ip_address(address)
        )
    except ValueError as exc:
        raise ProviderPolicyError(
            "ADDRESS_INVALID",
            "model endpoint resolved to an invalid address",
        ) from exc
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        parsed = parsed.ipv4_mapped
    if parsed.is_loopback and not allow_loopback:
        raise ProviderPolicyError(
            "LOOPBACK_DISABLED",
            "loopback model endpoints require an explicit local-only setting",
        )
    if (
        parsed.is_unspecified
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
    ):
        raise ProviderPolicyError(
            "ADDRESS_BLOCKED",
            "model endpoint resolved to a prohibited address class",
        )


def validate_model_base_url(
    value: str,
    *,
    allow_insecure_http: bool = False,
    allow_loopback: bool = False,
) -> str:
    supplied = str(value or "")
    if supplied != supplied.strip() or not supplied:
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "model base URL is missing or contains surrounding whitespace",
        )
    raw = supplied.rstrip("/")
    if any(ord(char) < 33 for char in raw):
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "model base URL contains whitespace or control characters",
        )
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("http", "https"):
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "model base URL must use http or https",
        )
    if parsed.scheme == "http" and not allow_insecure_http:
        raise ProviderPolicyError(
            "INSECURE_HTTP_DISABLED",
            "plain HTTP requires an explicit local/lab override",
        )
    if not parsed.hostname or parsed.username or parsed.password:
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "model base URL must contain a host and no embedded credentials",
        )
    if parsed.query or parsed.fragment:
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "query strings and fragments are not permitted",
        )
    if parsed.hostname.casefold().rstrip(".") in _BLOCKED_HOSTS:
        raise ProviderPolicyError(
            "HOST_BLOCKED",
            "cloud metadata hostnames are not permitted",
        )
    if "%" in parsed.hostname:
        raise ProviderPolicyError(
            "HOST_BLOCKED",
            "scoped IPv6 hosts are not permitted",
        )
    try:
        parsed.port
    except ValueError as exc:
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "model base URL contains an invalid port",
        ) from exc
    if any(segment in (".", "..") for segment in parsed.path.split("/")):
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "relative URL path segments are not permitted",
        )
    if not parsed.path.endswith("/v1"):
        raise ProviderPolicyError(
            "BASE_URL_INVALID",
            "OpenAI-compatible model base URL path must end with /v1",
        )
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        _validate_address(parsed.hostname, allow_loopback=allow_loopback)
    return raw


class JSONTransport(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]: ...


class StdlibJSONTransport:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def _resolve(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = socket.getaddrinfo(
                parsed.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise ProviderError(
                "DNS_FAILED",
                "model endpoint hostname could not be resolved",
            ) from exc
        if not addresses:
            raise ProviderError(
                "DNS_FAILED",
                "model endpoint resolved to no addresses",
            )
        for address in addresses:
            _validate_address(
                address[4][0],
                allow_loopback=self.config.allow_loopback,
            )

    def _ssl_context(self, url: str) -> ssl.SSLContext | None:
        if urllib.parse.urlsplit(url).scheme != "https":
            return None
        if self.config.tls_verify:
            return ssl.create_default_context(
                cafile=self.config.ca_bundle or None,
            )
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(raw) > self.config.max_request_bytes:
            raise ProviderPolicyError(
                "REQUEST_TOO_LARGE",
                "model request exceeds the configured byte limit",
            )
        self._resolve(url)
        request = urllib.request.Request(
            url,
            data=raw,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                **headers,
            },
            method="POST",
        )
        handlers: list[Any] = [
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        ]
        context = self._ssl_context(url)
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                body = response.read(self.config.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                f"HTTP_{exc.code}",
                "model endpoint rejected the request",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(
                "TRANSPORT_FAILED",
                "model endpoint request failed",
            ) from exc
        if len(body) > self.config.max_response_bytes:
            raise ProviderResponseError(
                "RESPONSE_TOO_LARGE",
                "model response exceeds the configured byte limit",
            )
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(
                "RESPONSE_JSON_INVALID",
                "model response is not valid UTF-8 JSON",
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "RESPONSE_SHAPE_INVALID",
                "model response root must be an object",
            )
        return decoded


class OpenAICompatibleProvider:
    """OpenAI-compatible chat completions without SDK/tool-call dependency."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        capabilities: ProviderCapabilities | None = None,
        transport: JSONTransport | None = None,
    ):
        self.config = config
        self.capabilities = capabilities or ProviderCapabilities()
        self.transport = transport or StdlibJSONTransport(config)

    @property
    def endpoint(self) -> str:
        return f"{self.config.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        if not self.config.auth_value:
            return {}
        return {self.config.auth_header: self.config.auth_value}

    @staticmethod
    def _validate_messages(
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        if not isinstance(messages, list) or not 1 <= len(messages) <= 64:
            raise ProviderPolicyError(
                "MESSAGES_INVALID",
                "messages must contain between 1 and 64 entries",
            )
        total = 0
        normalized: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ProviderPolicyError(
                    "MESSAGES_INVALID",
                    "each message must contain only role and content",
                )
            role = message.get("role")
            content = message.get("content")
            if role not in ("system", "user", "assistant") or not isinstance(
                content, str
            ):
                raise ProviderPolicyError(
                    "MESSAGES_INVALID",
                    "message role or content is invalid",
                )
            total += len(content.encode("utf-8"))
            normalized.append({"role": role, "content": content})
        if total > MAX_MESSAGE_BYTES:
            raise ProviderPolicyError(
                "MESSAGES_TOO_LARGE",
                "message content exceeds the configured trust-boundary limit",
            )
        return normalized

    def _generate(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None,
        grammar: str | None,
        constraint_mode: str,
        max_tokens: int,
        temperature: float,
        seed: int | None,
    ) -> str:
        if not 1 <= max_tokens <= 16_384:
            raise ProviderPolicyError(
                "MAX_TOKENS_INVALID",
                "max_tokens must be between 1 and 16384",
            )
        if not 0 <= temperature <= 2:
            raise ProviderPolicyError(
                "TEMPERATURE_INVALID",
                "temperature must be between 0 and 2",
            )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": self._validate_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if seed is not None:
            payload["seed"] = int(seed)
        if constraint_mode == "json_schema":
            if schema is None:
                raise ProviderPolicyError(
                    "SCHEMA_REQUIRED",
                    "JSON-schema constraint mode requires a schema",
                )
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "playbook_ir",
                    "strict": True,
                    "schema": schema,
                },
            }
        elif constraint_mode == "grammar":
            if not grammar:
                raise ProviderPolicyError(
                    "GRAMMAR_REQUIRED",
                    "grammar constraint mode requires a grammar",
                )
            payload["grammar"] = grammar
        elif constraint_mode != "none":
            raise ProviderPolicyError(
                "CONSTRAINT_MODE_INVALID",
                "constraint mode is not supported",
            )
        response = self.transport.post_json(
            self.endpoint,
            payload,
            self._headers(),
        )
        try:
            choices = response["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "RESPONSE_SHAPE_INVALID",
                "model response lacks choices[0].message.content",
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError(
                "RESPONSE_CONTENT_INVALID",
                "model response content must be a non-empty string",
            )
        return content

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        grammar: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        seed: int | None = 0,
    ) -> str:
        if schema is None and grammar is None:
            raise ProviderPolicyError(
                "CONSTRAINT_REQUIRED",
                "IR generation requires a JSON Schema or grammar",
            )
        mode = "none"
        if schema is not None and self.capabilities.json_schema:
            mode = "json_schema"
        elif grammar and self.capabilities.grammar:
            mode = "grammar"
        elif not self.config.allow_unconstrained_json:
            raise ProviderPolicyError(
                "CONSTRAINT_UNAVAILABLE",
                "endpoint has not proven a supported output constraint",
            )
        return self._generate(
            messages,
            schema=schema,
            grammar=grammar,
            constraint_mode=mode,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
        )

    def probe(self) -> ProviderCapabilities:
        """Probe schema then grammar support; unsupported constraints degrade."""
        messages = [{"role": "user", "content": "Return an empty JSON object."}]
        tiny_schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        schema_ok = False
        grammar_ok = False
        reachable = False
        errors: list[str] = []
        try:
            content = self._generate(
                messages,
                schema=tiny_schema,
                grammar=None,
                constraint_mode="json_schema",
                max_tokens=16,
                temperature=0,
                seed=0,
            )
            reachable = True
            schema_ok = self._is_empty_object(content)
            if not schema_ok:
                errors.append("json_schema:CONSTRAINT_IGNORED")
        except ProviderError as exc:
            errors.append(f"json_schema:{exc.code}")
        if not schema_ok:
            try:
                content = self._generate(
                    messages,
                    schema=None,
                    grammar='root ::= "{}"',
                    constraint_mode="grammar",
                    max_tokens=16,
                    temperature=0,
                    seed=0,
                )
                reachable = True
                grammar_ok = self._is_empty_object(content)
                if not grammar_ok:
                    errors.append("grammar:CONSTRAINT_IGNORED")
            except ProviderError as exc:
                errors.append(f"grammar:{exc.code}")
        if not reachable:
            try:
                self._generate(
                    messages,
                    schema=None,
                    grammar=None,
                    constraint_mode="none",
                    max_tokens=16,
                    temperature=0,
                    seed=0,
                )
                reachable = True
            except ProviderError as exc:
                errors.append(f"base:{exc.code}")
        return ProviderCapabilities(
            reachable=reachable,
            json_schema=schema_ok,
            grammar=grammar_ok,
            detail=",".join(errors),
        )

    @staticmethod
    def _is_empty_object(content: str) -> bool:
        try:
            return json.loads(content) == {}
        except json.JSONDecodeError:
            return False
