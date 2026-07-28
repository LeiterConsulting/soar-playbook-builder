"""Build, load, persist, and merge the capability index."""

from __future__ import annotations

import hashlib
import json
import os
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


def save_index(index: CapabilityIndex, path: Path | None = None) -> Path:
    target = path or index_storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = index.to_dict()
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return target


def load_index(path: Path | None = None) -> CapabilityIndex | None:
    target = path or index_storage_path()
    if not target.is_file():
        return None
    with open(target, encoding="utf-8") as fh:
        data = json.load(fh)
    return CapabilityIndex.from_dict(data)


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
    index = load_index(path=target)
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
            "harvest_errors": ["No persisted index — run rebuild capability index"],
            "stale": True,
            "baseline_only": True,
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
    }