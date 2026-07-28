"""Build, load, persist, and merge the capability index."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capability.introspect import harvest_all
from capability.schema import (
    ActionCapability,
    ActionParameter,
    AppCapability,
    CefField,
    CapabilityIndex,
    EgressTag,
)

_BASELINE_DIR = Path(__file__).resolve().parent / "baseline"
_DEFAULT_INDEX_DIR = Path(__file__).resolve().parent / ".index"
_INTEGRITY_KEY = "_integrity"


class IndexIntegrityError(ValueError):
    """A persisted capability index failed integrity or shape validation."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_baseline_apps() -> dict[str, AppCapability]:
    data = _load_json(_BASELINE_DIR / "apps.json")
    apps: dict[str, AppCapability] = {}
    for key, row in (data.get("apps") or {}).items():
        if not isinstance(row, dict):
            continue
        actions: list[ActionCapability] = []
        for act in row.get("actions") or []:
            if not isinstance(act, dict):
                continue
            params = [
                ActionParameter.from_rest(p) if isinstance(p, dict) else ActionParameter(name=str(p))
                for p in act.get("parameters") or []
            ]
            actions.append(
                ActionCapability(
                    name=str(act.get("name") or ""),
                    app=str(act.get("app") or key),
                    description=str(act.get("description") or ""),
                    parameters=params,
                    output_datapaths=list(act.get("output_datapaths") or []),
                    requires_egress=str(act.get("requires_egress") or "unknown"),  # type: ignore[arg-type]
                    source="baseline",
                    app_version=str(row.get("version") or ""),
                )
            )
        apps[key] = AppCapability(
            name=str(row.get("name") or key),
            product_name=str(row.get("product_name") or ""),
            version=str(row.get("version") or ""),
            actions=actions,
            source="baseline",
            first_seen=_utc_now(),
            last_verified=_utc_now(),
            configuration_keys=[
                str(item) for item in row.get("configuration_keys") or []
            ],
        )
    return apps


def load_baseline_cef() -> list[CefField]:
    data = _load_json(_BASELINE_DIR / "cef.json")
    return [
        CefField(
            name=str(row.get("name") or ""),
            contains=[str(c) for c in row.get("contains") or []],
            label=str(row.get("label") or ""),
        )
        for row in data.get("fields") or []
        if isinstance(row, dict) and row.get("name")
    ]


def load_egress_tags() -> dict[str, dict[str, str]]:
    data = _load_json(_BASELINE_DIR / "egress_tags.json")
    return dict(data.get("actions") or {})


def load_egress_substitutions() -> dict[str, dict[str, Any]]:
    data = _load_json(_BASELINE_DIR / "egress_tags.json")
    return dict(data.get("substitutions") or {})


def _merge_action(baseline: ActionCapability | None, discovered: ActionCapability | None) -> ActionCapability:
    if discovered and baseline:
        egress: EgressTag = discovered.requires_egress
        if egress == "unknown" and baseline.requires_egress != "unknown":
            egress = baseline.requires_egress
        return ActionCapability(
            name=discovered.name,
            app=discovered.app,
            description=discovered.description or baseline.description,
            parameters=discovered.parameters or baseline.parameters,
            output_datapaths=discovered.output_datapaths or baseline.output_datapaths,
            requires_egress=egress,
            source="merged",
            app_version=discovered.app_version or baseline.app_version,
        )
    if discovered:
        return discovered
    if baseline:
        return baseline
    raise ValueError("merge_action requires at least one action")


def merge_baseline(discovered: CapabilityIndex) -> CapabilityIndex:
    """Diff live harvest against baseline and return merged index."""
    baseline_apps = load_baseline_apps()
    baseline_cef = load_baseline_cef()
    merged_apps: dict[str, AppCapability] = {}

    all_keys = set(baseline_apps) | set(discovered.apps)
    for key in sorted(all_keys):
        base_app = baseline_apps.get(key)
        disc_app = discovered.apps.get(key)
        if disc_app and base_app:
            action_map: dict[str, ActionCapability] = {}
            for act in base_app.actions:
                action_map[act.name.lower()] = act
            merged_actions: list[ActionCapability] = []
            seen: set[str] = set()
            for act in disc_app.actions:
                merged = _merge_action(action_map.get(act.name.lower()), act)
                merged_actions.append(merged)
                seen.add(act.name.lower())
            for act in base_app.actions:
                if act.name.lower() not in seen:
                    merged_actions.append(act)
            merged_apps[key] = AppCapability(
                name=disc_app.name,
                product_name=disc_app.product_name or base_app.product_name,
                version=disc_app.version or base_app.version,
                actions=merged_actions,
                source="merged",
                first_seen=base_app.first_seen or _utc_now(),
                last_verified=disc_app.last_verified or _utc_now(),
                configuration_keys=(
                    disc_app.configuration_keys or base_app.configuration_keys
                ),
            )
        elif disc_app:
            merged_apps[key] = disc_app
        elif base_app:
            merged_apps[key] = base_app

    cef_names = {c.name for c in discovered.cef_fields}
    cef_fields = list(discovered.cef_fields)
    for field in baseline_cef:
        if field.name not in cef_names:
            cef_fields.append(field)

    return CapabilityIndex(
        version=discovered.version,
        index_version=_index_version(merged_apps),
        built_at=_utc_now(),
        harvest_status=discovered.harvest_status,
        harvest_errors=list(discovered.harvest_errors),
        apps=merged_apps,
        assets=list(discovered.assets),
        cef_fields=cef_fields,
        labels=discovered.labels or ["events", "investigation"],
        severities=discovered.severities or ["low", "medium", "high", "critical"],
        statuses=discovered.statuses or ["new", "open", "closed"],
        roles=list(discovered.roles),
        permission_principal=discovered.permission_principal,
        action_permissions=dict(discovered.action_permissions),
        permissions_status=discovered.permissions_status,
        custom_lists=list(discovered.custom_lists),
        custom_lists_status=discovered.custom_lists_status,
        playbooks=list(discovered.playbooks),
        playbooks_status=discovered.playbooks_status,
    )


def _index_version(apps: dict[str, AppCapability]) -> str:
    blob = json.dumps(
        {k: v.to_dict() for k, v in sorted(apps.items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def index_storage_path() -> Path:
    """Resolve writable path for persisted index (SOAR app data or module .index/)."""
    for getter in (
        lambda: __import__("phantom.app", fromlist=["phantom"]).get_app_local_data_path(),  # type: ignore[attr-defined]
        lambda: os.environ.get("SOAR_CAPABILITY_INDEX_DIR"),
    ):
        try:
            raw = getter()
            if raw:
                base = Path(str(raw))
                base.mkdir(parents=True, exist_ok=True)
                return base / "capability_index.json"
        except Exception:  # noqa: BLE001
            continue
    _DEFAULT_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_INDEX_DIR / "capability_index.json"


def _backup_path(target: Path) -> Path:
    return target.with_name(f"{target.stem}.last-good{target.suffix}")


def _lock_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.lock")


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    clean = dict(payload)
    clean.pop(_INTEGRITY_KEY, None)
    return json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _serialized_index(index: CapabilityIndex) -> bytes:
    payload = index.to_dict()
    payload[_INTEGRITY_KEY] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(_canonical_payload(payload)).hexdigest(),
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _index_from_bytes(raw: bytes) -> CapabilityIndex:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise IndexIntegrityError("capability index root must be an object")
    if not isinstance(data.get("apps"), dict):
        raise IndexIntegrityError("capability index apps must be an object")
    integrity = data.get(_INTEGRITY_KEY)
    if integrity is not None:
        if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
            raise IndexIntegrityError("capability index integrity metadata is invalid")
        expected = str(integrity.get("digest") or "")
        actual = hashlib.sha256(_canonical_payload(data)).hexdigest()
        if not expected or expected != actual:
            raise IndexIntegrityError("capability index checksum mismatch")
    index = CapabilityIndex.from_dict(data)
    if index.harvest_status not in {"ok", "partial", "failed"}:
        raise IndexIntegrityError("capability index harvest status is invalid")
    return index


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _index_lock(target: Path):
    lock = _lock_path(target)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+b") as handle:
        try:
            os.chmod(lock, 0o600)
        except OSError:
            pass
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            fcntl = None  # type: ignore[assignment]
        try:
            yield
        finally:
            if fcntl is not None:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


def save_index(index: CapabilityIndex, path: Path | None = None) -> Path:
    target = path or index_storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = _serialized_index(index)
    _index_from_bytes(serialized)
    with _index_lock(target):
        if target.is_file():
            try:
                previous = target.read_bytes()
                _index_from_bytes(previous)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, IndexIntegrityError, TypeError):
                pass
            else:
                _atomic_write(_backup_path(target), previous)
        _atomic_write(target, serialized)
    return target


def _load_index_with_status(
    path: Path | None = None,
) -> tuple[CapabilityIndex | None, bool, str]:
    target = path or index_storage_path()
    errors: list[str] = []
    for candidate, recovered in (
        (target, False),
        (_backup_path(target), True),
    ):
        if not candidate.is_file():
            continue
        try:
            return _index_from_bytes(candidate.read_bytes()), recovered, "; ".join(errors)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, IndexIntegrityError, TypeError) as exc:
            errors.append(f"{candidate.name}: {exc}")
    return None, False, "; ".join(errors)


def load_index(path: Path | None = None) -> CapabilityIndex | None:
    index, _, _ = _load_index_with_status(path)
    return index


def build_index(
    *,
    request: Any | None = None,
    rest_fn: Any | None = None,
    persist: bool = True,
    path: Path | None = None,
) -> tuple[CapabilityIndex, Path | None]:
    """Harvest live SOAR, merge baseline, optionally persist."""
    egress_map = load_egress_tags()
    baseline_cef = load_baseline_cef()
    discovered = harvest_all(rest_fn, request=request, egress_map=egress_map, baseline_cef=baseline_cef)

    if not discovered.apps:
        # No live harvest — seed from baseline only
        baseline_apps = load_baseline_apps()
        discovered = CapabilityIndex(
            built_at=_utc_now(),
            harvest_status="partial" if discovered.harvest_errors else "ok",
            harvest_errors=discovered.harvest_errors,
            apps=baseline_apps,
            assets=discovered.assets,
            cef_fields=baseline_cef,
            labels=discovered.labels or ["events", "investigation"],
            severities=discovered.severities,
            statuses=discovered.statuses,
        )
        merged = discovered
        merged.index_version = _index_version(merged.apps)
    else:
        merged = merge_baseline(discovered)

    saved: Path | None = None
    if persist:
        saved = save_index(merged, path=path)
    return merged, saved


def index_status(path: Path | None = None) -> dict[str, Any]:
    """Summary for connector action and environment UI."""
    target = path or index_storage_path()
    index, recovered, integrity_error = _load_index_with_status(path=target)
    if index is None:
        baseline = load_baseline_apps()
        return {
            "loaded": False,
            "path": str(target),
            "app_count": len(baseline),
            "action_count": sum(len(a.actions) for a in baseline.values()),
            "asset_count": 0,
            "index_version": "",
            "built_at": "",
            "harvest_status": "missing",
            "harvest_errors": [
                integrity_error or "No persisted index — run rebuild capability index"
            ],
            "stale": True,
            "baseline_only": True,
            "recovered_from_last_good": False,
            "integrity_error": integrity_error,
        }

    age_seconds = 0
    stale = False
    if index.built_at:
        try:
            built = datetime.fromisoformat(index.built_at.replace("Z", "+00:00"))
            age_seconds = int((datetime.now(timezone.utc) - built.astimezone(timezone.utc)).total_seconds())
            stale = age_seconds > 86400
        except ValueError:
            stale = True

    return {
        "loaded": True,
        "path": str(target),
        "app_count": len(index.apps),
        "action_count": sum(len(a.actions) for a in index.apps.values()),
        "asset_count": len(index.assets),
        "index_version": index.index_version,
        "built_at": index.built_at,
        "harvest_status": index.harvest_status,
        "harvest_errors": list(index.harvest_errors),
        "stale": stale,
        "index_age_seconds": age_seconds,
        "baseline_only": all(a.source == "baseline" for a in index.apps.values()),
        "labels_count": len(index.labels),
        "cef_field_count": len(index.cef_fields),
        "recovered_from_last_good": recovered,
        "integrity_error": integrity_error,
    }
