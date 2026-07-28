"""Capability index dataclasses — source of truth for SOAR apps, actions, assets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CapabilitySource = Literal["baseline", "discovered", "merged"]
EgressTag = Literal["true", "false", "unknown"]


@dataclass
class ActionParameter:
    name: str
    data_type: str = ""
    contains: list[str] = field(default_factory=list)
    required: bool = False
    description: str = ""
    default_value: Any = None

    @classmethod
    def from_rest(cls, row: dict[str, Any]) -> ActionParameter:
        contains = row.get("contains") or row.get("cef") or []
        if isinstance(contains, str):
            contains = [contains]
        return cls(
            name=str(row.get("name") or ""),
            data_type=str(row.get("data_type") or row.get("type") or ""),
            contains=[str(c) for c in contains if c],
            required=bool(row.get("required")),
            description=str(row.get("description") or ""),
            default_value=row.get("default_value"),
        )


@dataclass
class ActionCapability:
    name: str
    app: str
    description: str = ""
    parameters: list[ActionParameter] = field(default_factory=list)
    output_datapaths: list[str] = field(default_factory=list)
    requires_egress: EgressTag = "unknown"
    source: CapabilitySource = "discovered"
    app_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AppCapability:
    name: str
    product_name: str = ""
    version: str = ""
    actions: list[ActionCapability] = field(default_factory=list)
    source: CapabilitySource = "discovered"
    first_seen: str = ""
    last_verified: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "actions"},
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class AssetRecord:
    name: str
    app: str = ""
    product_name: str = ""
    product_code: str = ""
    configured: bool = True
    healthy: bool = True
    id: int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CefField:
    name: str
    contains: list[str] = field(default_factory=list)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityIndex:
    version: str = "1.0.0"
    index_version: str = ""
    built_at: str = ""
    harvest_status: Literal["ok", "partial", "failed"] = "ok"
    harvest_errors: list[str] = field(default_factory=list)
    apps: dict[str, AppCapability] = field(default_factory=dict)
    assets: list[AssetRecord] = field(default_factory=list)
    cef_fields: list[CefField] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "index_version": self.index_version,
            "built_at": self.built_at,
            "harvest_status": self.harvest_status,
            "harvest_errors": list(self.harvest_errors),
            "apps": {k: v.to_dict() for k, v in self.apps.items()},
            "assets": [a.to_dict() for a in self.assets],
            "cef_fields": [c.to_dict() for c in self.cef_fields],
            "labels": list(self.labels),
            "severities": list(self.severities),
            "statuses": list(self.statuses),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityIndex:
        apps: dict[str, AppCapability] = {}
        for key, row in (data.get("apps") or {}).items():
            if not isinstance(row, dict):
                continue
            actions = []
            for act in row.get("actions") or []:
                if not isinstance(act, dict):
                    continue
                params = [
                    ActionParameter(**p) if isinstance(p, dict) else ActionParameter(name=str(p))
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
                        source=str(act.get("source") or "discovered"),  # type: ignore[arg-type]
                        app_version=str(act.get("app_version") or ""),
                    )
                )
            apps[key] = AppCapability(
                name=str(row.get("name") or key),
                product_name=str(row.get("product_name") or ""),
                version=str(row.get("version") or ""),
                actions=actions,
                source=str(row.get("source") or "discovered"),  # type: ignore[arg-type]
                first_seen=str(row.get("first_seen") or ""),
                last_verified=str(row.get("last_verified") or ""),
            )
        assets = [
            AssetRecord(**a) if isinstance(a, dict) else AssetRecord(name=str(a))
            for a in data.get("assets") or []
        ]
        cef = [
            CefField(**c) if isinstance(c, dict) else CefField(name=str(c))
            for c in data.get("cef_fields") or []
        ]
        return cls(
            version=str(data.get("version") or "1.0.0"),
            index_version=str(data.get("index_version") or ""),
            built_at=str(data.get("built_at") or ""),
            harvest_status=str(data.get("harvest_status") or "ok"),  # type: ignore[arg-type]
            harvest_errors=[str(e) for e in data.get("harvest_errors") or []],
            apps=apps,
            assets=assets,
            cef_fields=cef,
            labels=[str(x) for x in data.get("labels") or []],
            severities=[str(x) for x in data.get("severities") or []],
            statuses=[str(x) for x in data.get("statuses") or []],
        )
