#!/usr/bin/env python3
"""Check repository-local Markdown links without network access."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK_RE = re.compile(
    r"!?\[[^\]]*]\(\s*(?P<target><[^>]+>|[^\s)]+)"
)
REMOTE_SCHEMES = {
    "app",
    "data",
    "file",
    "http",
    "https",
    "mailto",
    "tel",
}


def markdown_files(root: Path) -> list[Path]:
    paths = [
        path
        for path in root.glob("*.md")
        if path.is_file()
    ]
    paths.extend(
        path
        for path in (root / "docs").rglob("*.md")
        if path.is_file()
    )
    return sorted(set(paths))


def check_docs(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    for document in markdown_files(root):
        text = document.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = html.unescape(match.group("target")).strip("<>")
            if not raw or raw.startswith("#"):
                continue
            parsed = urlsplit(raw)
            if parsed.scheme.lower() in REMOTE_SCHEMES:
                continue
            if (
                raw.isupper()
                or any(marker in raw for marker in ("${", "{{", "<", ">"))
            ):
                continue
            relative_text = unquote(raw.split("#", 1)[0])
            if not relative_text:
                continue
            candidate = (
                root / relative_text.lstrip("/")
                if relative_text.startswith("/")
                else document.parent / relative_text
            ).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(
                    f"{document.relative_to(root)}: link escapes repository: {raw}"
                )
                continue
            if not candidate.exists():
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{document.relative_to(root)}:{line}: "
                    f"missing local link target {raw!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    errors = check_docs(args.root)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Markdown links OK ({len(markdown_files(args.root))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
