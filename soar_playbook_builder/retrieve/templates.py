"""Strict loader for shipped Playbook IR retrieval templates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ir.schema import PlaybookIR

MAX_TEMPLATE_FILES = 128
MAX_TEMPLATE_BYTES = 256 * 1024
DEFAULT_TEMPLATE_DIRECTORY = Path(__file__).with_name("templates")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class TemplateRecord:
    id: str
    ir: PlaybookIR
    sha256: str
    search_text: str
    source_path: str

    def context_dict(self) -> dict[str, object]:
        return {
            "template_id": self.id,
            "sha256": self.sha256,
            "ir": self.ir.to_dict(canonical=True),
        }


@dataclass(frozen=True)
class TemplateLibrary:
    records: tuple[TemplateRecord, ...]

    @classmethod
    def load(
        cls,
        directory: Path | str = DEFAULT_TEMPLATE_DIRECTORY,
    ) -> TemplateLibrary:
        root = Path(directory)
        if not root.is_dir():
            raise ValueError(f"template directory does not exist: {root}")
        paths = sorted(root.glob("*.json"), key=lambda item: item.name)
        if len(paths) > MAX_TEMPLATE_FILES:
            raise ValueError(
                f"template library exceeds {MAX_TEMPLATE_FILES} files"
            )
        records: list[TemplateRecord] = []
        seen: set[str] = set()
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"template path must be a regular file: {path.name}")
            raw = path.read_bytes()
            if len(raw) > MAX_TEMPLATE_BYTES:
                raise ValueError(
                    f"template exceeds {MAX_TEMPLATE_BYTES} bytes: {path.name}"
                )
            try:
                document = json.loads(
                    raw.decode("utf-8"),
                    object_pairs_hook=_unique_object,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(f"non-finite JSON constant: {value}")
                    ),
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid template JSON: {path.name}") from exc
            ir = PlaybookIR.from_dict(document)
            template_id = ir.metadata.template_id
            if not template_id:
                raise ValueError(
                    f"template metadata.template_id is required: {path.name}"
                )
            if template_id != path.stem:
                raise ValueError(
                    f"template id/path mismatch: {template_id!r} != {path.stem!r}"
                )
            if template_id in seen:
                raise ValueError(f"duplicate template id: {template_id}")
            seen.add(template_id)
            actions = [
                f"{getattr(node, 'app', '')} {getattr(node, 'action', '')}"
                for node in ir.nodes
                if node.type == "action"
            ]
            search_text = " ".join(
                (
                    template_id,
                    ir.name,
                    ir.description,
                    " ".join(ir.metadata.labels),
                    " ".join(actions),
                )
            )
            records.append(
                TemplateRecord(
                    id=template_id,
                    ir=ir,
                    sha256=ir.sha256(),
                    search_text=search_text,
                    source_path=path.name,
                )
            )
        return cls(records=tuple(sorted(records, key=lambda item: item.id)))

    def by_id(self) -> dict[str, TemplateRecord]:
        return {record.id: record for record in self.records}
