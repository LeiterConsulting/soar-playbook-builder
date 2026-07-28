"""Constrained, OpenAI-compatible IR generation boundary."""

from .decode import DecodeResult, GenerationContext, generate_ir
from .provider import (
    OpenAICompatibleProvider,
    ProviderCapabilities,
    ProviderConfig,
    ProviderError,
    ProviderPolicyError,
    ProviderResponseError,
    StdlibJSONTransport,
)

__all__ = [
    "DecodeResult",
    "GenerationContext",
    "OpenAICompatibleProvider",
    "ProviderCapabilities",
    "ProviderConfig",
    "ProviderError",
    "ProviderPolicyError",
    "ProviderResponseError",
    "StdlibJSONTransport",
    "generate_ir",
]
