"""No-model corpus spanning valid builds and deterministic seeded gaps."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from capability.schema import (
    ActionCapability,
    ActionParameter,
    AppCapability,
    AssetRecord,
    CapabilityIndex,
)
from ir.schema import PlaybookIR
from validate.fixtures import (
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
)

DocumentMutator = Callable[[dict[str, Any]], None]
IndexMutator = Callable[[CapabilityIndex], None]


@dataclass(frozen=True)
class CorpusCase:
    id: str
    request: str
    ir: PlaybookIR
    index: CapabilityIndex
    expected_status: str
    expected_gap_ids: tuple[str, ...]
    evaluated_at: str = FIXTURE_EVALUATED_AT


def _action(document: dict[str, Any]) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "action")


def _decision(document: dict[str, Any]) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "decision")


def _join(document: dict[str, Any]) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "join")


def _base_case(
    case_id: str,
    request: str,
    *,
    expected_status: str,
    expected_gap_ids: tuple[str, ...] = (),
    mutate_document: DocumentMutator | None = None,
    mutate_index: IndexMutator | None = None,
) -> CorpusCase:
    document = qualified_smoke_document()
    index = qualified_smoke_index()
    if mutate_document:
        mutate_document(document)
    if mutate_index:
        mutate_index(index)
    return CorpusCase(
        id=case_id,
        request=request,
        ir=PlaybookIR.from_dict(document),
        index=index,
        expected_status=expected_status,
        expected_gap_ids=tuple(sorted(expected_gap_ids)),
    )


def _set_asset(document: dict[str, Any], value: dict[str, Any]) -> None:
    _action(document)["asset"] = value


def _set_action_field(document: dict[str, Any], key: str, value: Any) -> None:
    _action(document)[key] = value


def _set_index_asset(index: CapabilityIndex, key: str, value: Any) -> None:
    setattr(index.assets[0], key, value)


def _set_index_action(index: CapabilityIndex, key: str, value: Any) -> None:
    setattr(index.apps["okta"].actions[0], key, value)


def _single_document(
    *,
    app: str,
    action: str,
    parameters: dict[str, Any],
    mode: str,
    asset_name: str = "asset_one",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": f"{app.replace('_', '-')}-{action.replace(' ', '-')}",
        "name": f"{app} {action}",
        "description": "No-model corpus fixture.",
        "entrypoint": "start",
        "nodes": [
            {"id": "start", "type": "start", "next": "run"},
            {
                "id": "run",
                "type": "action",
                "app": app,
                "action": action,
                "asset": {"kind": "asset", "name": asset_name},
                "parameters": parameters,
                "on_success": "complete",
                "on_failure": "failed",
            },
            {"id": "complete", "type": "end", "outcome": "success"},
            {"id": "failed", "type": "end", "outcome": "failure"},
        ],
        "metadata": {
            "capability_index_version": f"{app}-fixture-v1",
            "operating_mode": mode,
            "template_id": f"corpus-{app}-{action.replace(' ', '-')}",
        },
    }


def _single_index(
    *,
    app: str,
    action: ActionCapability,
    needs_asset: bool = True,
    custom_lists: list[str] | None = None,
    custom_lists_status: str = "verified",
    playbooks: list[str] | None = None,
    playbooks_status: str = "verified",
    severities: list[str] | None = None,
) -> CapabilityIndex:
    return CapabilityIndex(
        index_version=f"{app}-fixture-v1",
        built_at=FIXTURE_EVALUATED_AT,
        apps={
            app: AppCapability(
                name=app,
                product_name=app,
                version="test-only",
                actions=[action],
                source="discovered",
            )
        },
        assets=(
            [
                AssetRecord(
                    name="asset_one",
                    app=app,
                    configured=True,
                    healthy=True,
                    id=1,
                )
            ]
            if needs_asset
            else []
        ),
        severities=severities or ["low", "medium", "high", "critical"],
        permission_principal="corpus-principal",
        action_permissions={f"{app}:{action.name}": "allowed"},
        permissions_status="verified",
        custom_lists=list(custom_lists or []),
        custom_lists_status=custom_lists_status,  # type: ignore[arg-type]
        playbooks=list(playbooks or []),
        playbooks_status=playbooks_status,  # type: ignore[arg-type]
    )


def _single_case(
    case_id: str,
    request: str,
    *,
    document: dict[str, Any],
    index: CapabilityIndex,
    expected_status: str,
    expected_gap_ids: tuple[str, ...],
) -> CorpusCase:
    return CorpusCase(
        id=case_id,
        request=request,
        ir=PlaybookIR.from_dict(document),
        index=index,
        expected_status=expected_status,
        expected_gap_ids=tuple(sorted(expected_gap_ids)),
    )


def no_model_cases() -> tuple[CorpusCase, ...]:
    """Return fixed cases; constructing them performs no network access."""
    cases = [
        _base_case(
            "01_okta_all_nodes_clean",
            "Look up an Okta user and request analyst approval",
            expected_status="ok",
        ),
        _base_case(
            "02_asset_unbound",
            "Build the workflow but leave asset selection unresolved",
            expected_status="blocked",
            expected_gap_ids=("ASSET_UNBOUND",),
            mutate_document=lambda doc: _set_asset(
                doc, {"kind": "asset_unbound"}
            ),
        ),
        _base_case(
            "03_asset_missing",
            "Use an Okta asset that is not configured",
            expected_status="blocked",
            expected_gap_ids=("ASSET_MISSING",),
            mutate_document=lambda doc: _set_asset(
                doc, {"kind": "asset", "name": "does_not_exist"}
            ),
        ),
        _base_case(
            "04_asset_wrong_connector",
            "Accidentally bind a ServiceNow-owned asset to Okta",
            expected_status="blocked",
            expected_gap_ids=("ASSET_APP_MISMATCH",),
            mutate_index=lambda index: _set_index_asset(
                index, "app", "servicenow"
            ),
        ),
        _base_case(
            "05_asset_not_configured",
            "Use a saved but incomplete connector asset",
            expected_status="blocked",
            expected_gap_ids=("ASSET_NOT_CONFIGURED",),
            mutate_index=lambda index: _set_index_asset(
                index, "configured", False
            ),
        ),
        _base_case(
            "06_asset_unhealthy",
            "Use an asset whose connectivity test is failing",
            expected_status="blocked",
            expected_gap_ids=("ASSET_UNHEALTHY",),
            mutate_index=lambda index: _set_index_asset(
                index, "healthy", False
            ),
        ),
        _base_case(
            "07_app_impossible",
            "Use a connector that is not present in the catalog",
            expected_status="blocked",
            expected_gap_ids=("ACTION_APP_UNKNOWN",),
            mutate_document=lambda doc: _set_action_field(
                doc, "app", "invented_connector"
            ),
        ),
        _base_case(
            "08_action_impossible",
            "Run an invented action on an otherwise known app",
            expected_status="blocked",
            expected_gap_ids=("ACTION_NOT_FOUND",),
            mutate_document=lambda doc: _set_action_field(
                doc, "action", "invented action"
            ),
        ),
        _base_case(
            "09_baseline_app_not_install_evidence",
            "Use an app known only from the shipped baseline",
            expected_status="blocked",
            expected_gap_ids=("APP_INSTALLATION_UNVERIFIED",),
            mutate_index=lambda index: setattr(
                index.apps["okta"], "source", "baseline"
            ),
        ),
        _base_case(
            "10_baseline_action_not_install_evidence",
            "Use an action not observed in the installed app",
            expected_status="blocked",
            expected_gap_ids=("ACTION_INSTALLATION_UNVERIFIED",),
            mutate_index=lambda index: _set_index_action(
                index, "source", "baseline"
            ),
        ),
        _base_case(
            "11_required_parameter_missing",
            "Omit the required username",
            expected_status="blocked",
            expected_gap_ids=("PARAMETER_REQUIRED",),
            mutate_document=lambda doc: _set_action_field(
                doc, "parameters", {}
            ),
        ),
        _base_case(
            "12_unknown_parameter",
            "Add a parameter the connector does not declare",
            expected_status="blocked",
            expected_gap_ids=("PARAMETER_UNKNOWN",),
            mutate_document=lambda doc: _action(doc)["parameters"].update(
                {"invented": {"kind": "literal", "value": "x"}}
            ),
        ),
        _base_case(
            "13_literal_type_and_contains_mismatch",
            "Pass a number where a username is required",
            expected_status="blocked",
            expected_gap_ids=(
                "CONTAINS_MISMATCH",
                "PARAMETER_TYPE_MISMATCH",
            ),
            mutate_document=lambda doc: _action(doc)["parameters"].update(
                {"username": {"kind": "literal", "value": 7}}
            ),
        ),
        _base_case(
            "14_contains_mismatch",
            "Bind an IP field into a username parameter",
            expected_status="blocked",
            expected_gap_ids=("CONTAINS_MISMATCH",),
            mutate_document=lambda doc: _action(doc)["parameters"][
                "username"
            ].update({"path": ["cef", "sourceAddress"]}),
        ),
        _base_case(
            "15_unknown_cef",
            "Bind an artifact field absent from the local CEF catalog",
            expected_status="blocked",
            expected_gap_ids=("CONTAINS_UNVERIFIED", "DATAPATH_UNKNOWN"),
            mutate_document=lambda doc: _action(doc)["parameters"][
                "username"
            ].update({"path": ["cef", "inventedField"]}),
        ),
        _base_case(
            "16_undeclared_playbook_input",
            "Use an input that the IR does not declare",
            expected_status="blocked",
            expected_gap_ids=(
                "CONTAINS_UNVERIFIED",
                "PLAYBOOK_INPUT_UNDECLARED",
            ),
            mutate_document=lambda doc: _action(doc)["parameters"].update(
                {
                    "username": {
                        "kind": "datapath",
                        "scope": "playbook_input",
                        "path": ["username"],
                    }
                }
            ),
        ),
        _base_case(
            "17_unknown_action_output",
            "Use an output absent from the installed action metadata",
            expected_status="blocked",
            expected_gap_ids=("OUTPUT_DATAPATH_UNKNOWN",),
            mutate_document=lambda doc: _decision(doc)["condition"][
                "value"
            ].update({"path": ["data", "*", "invented"]}),
        ),
        _base_case(
            "18_permission_unavailable",
            "Run without principal permission evidence",
            expected_status="blocked",
            expected_gap_ids=("PERMISSION_UNVERIFIED",),
            mutate_index=lambda index: (
                setattr(index, "permissions_status", "unavailable"),
                setattr(index, "action_permissions", {}),
            ),
        ),
        _base_case(
            "19_permission_denied",
            "Run an action denied to the execution principal",
            expected_status="blocked",
            expected_gap_ids=("PERMISSION_DENIED",),
            mutate_index=lambda index: index.action_permissions.update(
                {"okta:get user": "denied"}
            ),
        ),
        _base_case(
            "20_egress_required_airgap",
            "Call an egress action from an air-gapped deployment",
            expected_status="blocked",
            expected_gap_ids=("EGRESS_REQUIRED",),
            mutate_index=lambda index: _set_index_action(
                index, "requires_egress", "true"
            ),
        ),
        _base_case(
            "21_egress_unknown_airgap",
            "Use an unclassified action in air-gapped mode",
            expected_status="blocked",
            expected_gap_ids=("EGRESS_UNKNOWN",),
            mutate_index=lambda index: _set_index_action(
                index, "requires_egress", "unknown"
            ),
        ),
        _base_case(
            "22_egress_unknown_connected",
            "Use an unclassified action in connected mode",
            expected_status="degraded",
            expected_gap_ids=("EGRESS_UNKNOWN",),
            mutate_document=lambda doc: doc["metadata"].update(
                {"operating_mode": "connected"}
            ),
            mutate_index=lambda index: _set_index_action(
                index, "requires_egress", "unknown"
            ),
        ),
        _base_case(
            "23_index_stale",
            "Validate against a week-old capability snapshot",
            expected_status="degraded",
            expected_gap_ids=("INDEX_STALE",),
            mutate_index=lambda index: setattr(
                index, "built_at", "2026-07-20T16:00:00+00:00"
            ),
        ),
        _base_case(
            "24_harvest_partial",
            "Validate after a partially failed capability refresh",
            expected_status="degraded",
            expected_gap_ids=("INDEX_HARVEST_DEGRADED",),
            mutate_index=lambda index: (
                setattr(index, "harvest_status", "partial"),
                setattr(index, "harvest_errors", ["asset endpoint denied"]),
            ),
        ),
        _base_case(
            "25_index_version_mismatch",
            "Compile an IR grounded on a different index",
            expected_status="blocked",
            expected_gap_ids=("CAPABILITY_INDEX_VERSION_MISMATCH",),
            mutate_document=lambda doc: doc["metadata"].update(
                {"capability_index_version": "old-index"}
            ),
        ),
        _base_case(
            "26_index_timestamp_missing",
            "Validate an index with no age evidence",
            expected_status="degraded",
            expected_gap_ids=("INDEX_TIMESTAMP_MISSING",),
            mutate_index=lambda index: setattr(index, "built_at", ""),
        ),
        _base_case(
            "27_all_join_without_fork",
            "Wait for every branch even though no fork exists",
            expected_status="blocked",
            expected_gap_ids=("ALL_JOIN_UNREACHABLE",),
            mutate_document=lambda doc: _join(doc).update({"strategy": "all"}),
        ),
        _base_case(
            "28_dynamic_custom_field",
            "Read a dynamic container field absent from inventory",
            expected_status="degraded",
            expected_gap_ids=("CONTAINS_UNVERIFIED", "DATAPATH_UNVERIFIED"),
            mutate_document=lambda doc: _action(doc)["parameters"].update(
                {
                    "username": {
                        "kind": "datapath",
                        "scope": "container",
                        "path": ["custom_fields", "username"],
                    }
                }
            ),
        ),
        _base_case(
            "29_multi_gap_asset_permission",
            "Leave the asset unresolved and permission evidence unavailable",
            expected_status="blocked",
            expected_gap_ids=("ASSET_UNBOUND", "PERMISSION_UNVERIFIED"),
            mutate_document=lambda doc: _set_asset(
                doc, {"kind": "asset_unbound"}
            ),
            mutate_index=lambda index: (
                setattr(index, "permissions_status", "unavailable"),
                setattr(index, "action_permissions", {}),
            ),
        ),
        _base_case(
            "30_connected_egress_allowed",
            "Use a classified egress action in connected mode",
            expected_status="ok",
            mutate_document=lambda doc: doc["metadata"].update(
                {"operating_mode": "connected"}
            ),
            mutate_index=lambda index: _set_index_action(
                index, "requires_egress", "true"
            ),
        ),
        _base_case(
            "31_index_clock_skew",
            "Validate an index timestamped in the future",
            expected_status="degraded",
            expected_gap_ids=("INDEX_TIMESTAMP_MISSING",),
            mutate_index=lambda index: setattr(
                index, "built_at", "2026-07-29T16:00:00+00:00"
            ),
        ),
    ]

    vt_action = ActionCapability(
        name="file reputation",
        app="virustotalv3",
        parameters=[
            ActionParameter(
                name="hash",
                data_type="string",
                contains=["hash"],
                required=True,
            )
        ],
        requires_egress="true",
        source="discovered",
    )
    cases.append(
        _single_case(
            "32_virustotal_offline_substitution",
            "Enrich a file hash with VirusTotal in air-gapped mode",
            document=_single_document(
                app="virustotalv3",
                action="file reputation",
                parameters={
                    "hash": {"kind": "literal", "value": "a" * 64}
                },
                mode="air_gapped",
            ),
            index=_single_index(app="virustotalv3", action=vt_action),
            expected_status="blocked",
            expected_gap_ids=("EGRESS_REQUIRED",),
        )
    )

    slack_action = ActionCapability(
        name="send message",
        app="slack",
        parameters=[
            ActionParameter(name="channel", data_type="string", required=True),
            ActionParameter(name="message", data_type="string", required=True),
        ],
        requires_egress="true",
        source="discovered",
    )
    cases.append(
        _single_case(
            "33_slack_connected_clean",
            "Notify the SOC channel in connected mode",
            document=_single_document(
                app="slack",
                action="send message",
                parameters={
                    "channel": {"kind": "literal", "value": "#soc"},
                    "message": {"kind": "literal", "value": "Case opened"},
                },
                mode="connected",
            ),
            index=_single_index(app="slack", action=slack_action),
            expected_status="ok",
            expected_gap_ids=(),
        )
    )

    snow_action = ActionCapability(
        name="create ticket",
        app="servicenow",
        parameters=[
            ActionParameter(
                name="short_description",
                data_type="string",
                required=True,
            )
        ],
        requires_egress="true",
        source="discovered",
    )
    cases.append(
        _single_case(
            "34_servicenow_restricted_blocked",
            "Create a ServiceNow ticket in restricted mode",
            document=_single_document(
                app="servicenow",
                action="create ticket",
                parameters={
                    "short_description": {
                        "kind": "literal",
                        "value": "Critical case",
                    }
                },
                mode="restricted",
            ),
            index=_single_index(app="servicenow", action=snow_action),
            expected_status="blocked",
            expected_gap_ids=("EGRESS_REQUIRED",),
        )
    )

    add_list = ActionCapability(
        name="add list",
        app="phantom",
        parameters=[
            ActionParameter(name="list_name", data_type="string", required=True),
            ActionParameter(name="value", data_type="string", required=True),
        ],
        requires_egress="false",
        source="discovered",
    )
    list_document = _single_document(
        app="phantom",
        action="add list",
        asset_name="not_used",
        parameters={
            "list_name": {
                "kind": "literal",
                "value": "local_threat_intel",
            },
            "value": {"kind": "literal", "value": "example.test"},
        },
        mode="air_gapped",
    )
    cases.append(
        _single_case(
            "35_custom_list_missing",
            "Write an indicator to a custom list that does not exist",
            document=list_document,
            index=_single_index(
                app="phantom",
                action=add_list,
                needs_asset=False,
                custom_lists=[],
            ),
            expected_status="blocked",
            expected_gap_ids=(
                "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
                "REFERENCED_OBJECT_MISSING",
            ),
        )
    )
    cases.append(
        _single_case(
            "36_custom_list_inventory_unavailable",
            "Write an indicator before custom lists were harvested",
            document=copy.deepcopy(list_document),
            index=_single_index(
                app="phantom",
                action=copy.deepcopy(add_list),
                needs_asset=False,
                custom_lists_status="unavailable",
            ),
            expected_status="blocked",
            expected_gap_ids=(
                "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
                "OBJECT_INVENTORY_UNAVAILABLE",
            ),
        )
    )

    run_playbook = ActionCapability(
        name="run playbook",
        app="phantom",
        parameters=[
            ActionParameter(name="playbook", data_type="string", required=True),
            ActionParameter(name="container", data_type="numeric", required=True),
        ],
        requires_egress="false",
        source="discovered",
    )
    cases.append(
        _single_case(
            "37_child_playbook_missing",
            "Run a child playbook absent from the local repository",
            document=_single_document(
                app="phantom",
                action="run playbook",
                asset_name="not_used",
                parameters={
                    "playbook": {
                        "kind": "literal",
                        "value": "local/missing_playbook",
                    },
                    "container": {"kind": "literal", "value": 42},
                },
                mode="air_gapped",
            ),
            index=_single_index(
                app="phantom",
                action=run_playbook,
                needs_asset=False,
                playbooks=[],
            ),
            expected_status="blocked",
            expected_gap_ids=(
                "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
                "REFERENCED_OBJECT_MISSING",
            ),
        )
    )

    set_severity = ActionCapability(
        name="set severity",
        app="phantom",
        parameters=[
            ActionParameter(
                name="severity",
                data_type="string",
                contains=["severity"],
                required=True,
            ),
            ActionParameter(name="container", data_type="numeric", required=True),
        ],
        requires_egress="false",
        source="discovered",
    )
    cases.append(
        _single_case(
            "38_invalid_severity",
            "Set a severity value absent from the local vocabulary",
            document=_single_document(
                app="phantom",
                action="set severity",
                asset_name="not_used",
                parameters={
                    "severity": {"kind": "literal", "value": "urgent"},
                    "container": {"kind": "literal", "value": 42},
                },
                mode="air_gapped",
            ),
            index=_single_index(
                app="phantom",
                action=set_severity,
                needs_asset=False,
                severities=["low", "medium", "high", "critical"],
            ),
            expected_status="blocked",
            expected_gap_ids=(
                "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
                "CONTAINS_MISMATCH",
                "REFERENCED_OBJECT_MISSING",
            ),
        )
    )

    disable_ad = ActionCapability(
        name="disable account",
        app="active_directory",
        parameters=[
            ActionParameter(
                name="username",
                data_type="string",
                contains=["username"],
                required=True,
            )
        ],
        requires_egress="false",
        source="discovered",
    )
    disable_document = _single_document(
        app="active_directory",
        action="disable account",
        parameters={
            "username": {"kind": "literal", "value": "example.user"}
        },
        mode="air_gapped",
    )
    cases.append(
        _single_case(
            "39_destructive_action_without_prompt",
            "Disable an Active Directory account without analyst approval",
            document=disable_document,
            index=_single_index(
                app="active_directory",
                action=disable_ad,
            ),
            expected_status="blocked",
            expected_gap_ids=("DESTRUCTIVE_ACTION_REVIEW_REQUIRED",),
        )
    )
    approved_document = copy.deepcopy(disable_document)
    approved_document["nodes"][0]["next"] = "approval"
    approved_document["nodes"].insert(
        1,
        {
            "id": "approval",
            "type": "prompt",
            "message": "Approve disabling this account?",
            "response_key": "approval",
            "choices": ["Approve", "Reject"],
            "on_success": "run",
            "on_failure": "failed",
            "on_timeout": "failed",
        },
    )
    cases.append(
        _single_case(
            "40_destructive_action_with_prompt",
            "Prompt an analyst before disabling an Active Directory account",
            document=approved_document,
            index=_single_index(
                app="active_directory",
                action=copy.deepcopy(disable_ad),
            ),
            expected_status="ok",
            expected_gap_ids=(),
        )
    )
    return tuple(cases)
