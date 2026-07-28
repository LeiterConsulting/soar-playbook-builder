"""Security headers for SOAR REST-handler responses."""

from __future__ import annotations

from typing import Any

HTML_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'none'",
        "base-uri 'self'",
        "connect-src 'self'",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        "img-src 'self' data:",
        "object-src 'none'",
        "script-src 'self'",
        # React uses bounded style attributes for resizable pane dimensions.
        # Scripts remain strict; no inline JavaScript is permitted.
        "style-src 'self' 'unsafe-inline'",
    )
)

NON_DOCUMENT_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'"
)


def apply_security_headers(response: Any, *, html_document: bool = False) -> Any:
    """Apply headers without depending on Django at import time."""
    response["Cache-Control"] = "no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    response["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    response["X-Frame-Options"] = "SAMEORIGIN" if html_document else "DENY"
    response["Content-Security-Policy"] = (
        HTML_CONTENT_SECURITY_POLICY
        if html_document
        else NON_DOCUMENT_CONTENT_SECURITY_POLICY
    )
    return response
