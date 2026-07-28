"""Synthetic, non-production fixtures for deterministic validator gates."""

from __future__ import annotations

import copy
from typing import Any

from capability.index import load_baseline_cef
from capability.schema import (
    ActionCapability,
    ActionParameter,
    AppCapability,
    AssetRecord,
    CapabilityIndex,
)
from ir.fixtures import smoke_ir_document
from ir.schema import PlaybookIR

FIXTURE_EVALUATED_AT = "2026-07-28T16:00:00+00:00"


def qualified_smoke_document() -> dict[str, Any]:
    document = copy.deepcopy(smoke_ir_document())
    document["metadata"]["capability_index_version"] = "qualified-v1"
    action = next(node for node in document["nodes"] if node["type"] == "action")
    action["asset"] = {"kind": "asset", "name": "okta_lab"}
    return document


def qualified_smoke_ir() -> PlaybookIR:
    return PlaybookIR.from_dict(qualified_smoke_document())


def qualified_smoke_index() -> CapabilityIndex:
    action = ActionCapability(
        name="get user",
        app="okta",
        description="Synthetic test capability; not production evidence.",
        parameters=[
            ActionParameter(
                name="username",
                data_type="string",
                contains=["username"],
                required=True,
            )
        ],
        output_datapaths=["action_result.data.*.id"],
        requires_egress="false",
        source="discovered",
        app_version="test-only",
    )
    return CapabilityIndex(
        index_version="qualified-v1",
        built_at=FIXTURE_EVALUATED_AT,
        harvest_status="ok",
        apps={
            "okta": AppCapability(
                name="okta",
                product_name="Okta",
                version="test-only",
                actions=[action],
                source="discovered",
                last_verified=FIXTURE_EVALUATED_AT,
                configuration_keys=["base_url", "token"],
            )
        },
        assets=[
            AssetRecord(
                name="okta_lab",
                app="okta",
                product_name="Okta",
                configured=True,
                healthy=True,
                id=1,
            )
        ],
        cef_fields=load_baseline_cef(),
        labels=["events"],
        severities=["low", "medium", "high", "critical"],
        statuses=["new", "open", "closed"],
        roles=["Automation"],
        permission_principal="synthetic-test-principal",
        action_permissions={"okta:get user": "allowed"},
        permissions_status="verified",
        custom_lists=[],
        custom_lists_status="verified",
        playbooks=[],
        playbooks_status="verified",
    )
