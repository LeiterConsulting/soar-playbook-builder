"""Context-safe rendering for the app's small, static HTML shells."""

from __future__ import annotations

import html
from pathlib import Path


def render_html_template(
    template_dir: Path,
    name: str,
    replacements: dict[str, object],
) -> str:
    """Render allowlisted placeholders as HTML text/attribute values.

    Templates must read injected values from HTML text or attributes. Values are
    never safe to place directly into JavaScript, CSS, URLs, or element names.
    """
    if Path(name).name != name or not name.endswith(".html"):
        raise ValueError("template name must be a local .html filename")

    path = template_dir / name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        safe_name = html.escape(name, quote=True)
        return f"<html><body>Missing template: {safe_name}</body></html>"

    for key, value in replacements.items():
        escaped = html.escape(str(value or ""), quote=True)
        text = text.replace("{{" + key + "}}", escaped)
    return text
