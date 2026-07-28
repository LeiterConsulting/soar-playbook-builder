"""Capability-index and IR-template retrieval with bounded context output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from capability.schema import ActionCapability, AppCapability, CapabilityIndex

from .bm25 import BM25Index, SearchDocument
from .templates import TemplateLibrary, TemplateRecord

MAX_ACTION_RESULTS = 32
MAX_TEMPLATE_RESULTS = 8
MAX_ASSET_CONTEXT = 64


@dataclass(frozen=True)
class RetrievedAction:
    id: str
    score: float
    app_key: str
    app: AppCapability
    action: ActionCapability

    def context_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 8),
            "app_key": self.app_key,
            "app": self.app.name,
            "product_name": self.app.product_name,
            "app_version": self.app.version,
            "source": self.action.source,
            "action": self.action.name,
            "description": self.action.description,
            "requires_egress": self.action.requires_egress,
            "parameters": [
                {
                    "name": parameter.name,
                    "type": parameter.data_type,
                    "contains": sorted(parameter.contains),
                    "required": parameter.required,
                    "description": parameter.description,
                }
                for parameter in sorted(
                    self.action.parameters,
                    key=lambda item: item.name.casefold(),
                )
            ],
            "outputs": sorted(self.action.output_datapaths),
        }


@dataclass(frozen=True)
class RetrievedTemplate:
    id: str
    score: float
    record: TemplateRecord

    def context_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 8),
            **self.record.context_dict(),
        }


@dataclass(frozen=True)
class RetrievalBundle:
    query: str
    index_version: str
    actions: tuple[RetrievedAction, ...]
    templates: tuple[RetrievedTemplate, ...]
    assets: tuple[dict[str, Any], ...]

    def context_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "index_version": self.index_version,
            "actions": [item.context_dict() for item in self.actions],
            "templates": [
                item.context_dict() for item in self.templates
            ],
            "assets": list(self.assets),
        }


class OfflineRetriever:
    def __init__(self, template_library: TemplateLibrary | None = None):
        self.template_library = template_library or TemplateLibrary.load()

    @staticmethod
    def _action_documents(
        index: CapabilityIndex,
    ) -> tuple[SearchDocument, ...]:
        documents: list[SearchDocument] = []
        for app_key in sorted(index.apps):
            app = index.apps[app_key]
            for action in sorted(
                app.actions,
                key=lambda item: item.name.casefold(),
            ):
                action_id = f"{app_key}:{action.name}"
                text = " ".join(
                    [
                        app_key,
                        app.name,
                        app.product_name,
                        action.name,
                        action.description,
                        " ".join(
                            " ".join(
                                (
                                    parameter.name,
                                    parameter.description,
                                    parameter.data_type,
                                    " ".join(parameter.contains),
                                )
                            )
                            for parameter in action.parameters
                        ),
                        " ".join(action.output_datapaths),
                    ]
                )
                documents.append(
                    SearchDocument(
                        id=action_id,
                        text=text,
                        payload=(app_key, app, action),
                    )
                )
        return tuple(documents)

    def retrieve(
        self,
        query: str,
        index: CapabilityIndex,
        *,
        action_limit: int = 12,
        template_limit: int = 3,
    ) -> RetrievalBundle:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("retrieval query must be a non-empty string")
        if not 1 <= action_limit <= MAX_ACTION_RESULTS:
            raise ValueError(
                f"action_limit must be between 1 and {MAX_ACTION_RESULTS}"
            )
        if not 1 <= template_limit <= MAX_TEMPLATE_RESULTS:
            raise ValueError(
                f"template_limit must be between 1 and {MAX_TEMPLATE_RESULTS}"
            )
        action_index = BM25Index(self._action_documents(index))
        action_results = tuple(
            RetrievedAction(
                id=result.document.id,
                score=result.score,
                app_key=result.document.payload[0],
                app=result.document.payload[1],
                action=result.document.payload[2],
            )
            for result in action_index.search(query, limit=action_limit)
        )
        template_documents = tuple(
            SearchDocument(
                id=record.id,
                text=record.search_text,
                payload=record,
            )
            for record in self.template_library.records
        )
        template_index = BM25Index(template_documents)
        template_results = tuple(
            RetrievedTemplate(
                id=result.document.id,
                score=result.score,
                record=result.document.payload,
            )
            for result in template_index.search(
                query,
                limit=template_limit,
            )
        )
        selected_apps = {item.app_key for item in action_results}
        for item in template_results:
            for node in item.record.ir.nodes:
                if node.type == "action":
                    selected_apps.add(getattr(node, "app", ""))
        assets = tuple(
            {
                "name": asset.name,
                "app": asset.app,
                "configured": asset.configured,
                "healthy": asset.healthy,
            }
            for asset in sorted(
                index.assets,
                key=lambda item: (item.app.casefold(), item.name.casefold()),
            )
            if asset.app in selected_apps
        )[:MAX_ASSET_CONTEXT]
        return RetrievalBundle(
            query=query,
            index_version=index.index_version or index.version,
            actions=action_results,
            templates=template_results,
            assets=assets,
        )
