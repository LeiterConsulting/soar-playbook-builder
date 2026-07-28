"""Seeded rule coverage for deterministic IR preflight."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from capability.schema import (  # noqa: E402
    ActionCapability,
    ActionParameter,
    AppCapability,
    AssetRecord,
    CapabilityIndex,
)
from ir.schema import PlaybookIR  # noqa: E402
from validate import preflight  # noqa: E402
from validate.fixtures import (  # noqa: E402
    FIXTURE_EVALUATED_AT,
    qualified_smoke_document,
    qualified_smoke_index,
    qualified_smoke_ir,
)


def _ids(report: Any) -> set[str]:
    return {gap.id for gap in report.gaps}


def _run(document: dict[str, Any], index: CapabilityIndex | None = None):
    return preflight(
        PlaybookIR.from_dict(document),
        index or qualified_smoke_index(),
        evaluated_at=FIXTURE_EVALUATED_AT,
    )


def _action(document: dict[str, Any]) -> dict[str, Any]:
    return next(node for node in document["nodes"] if node["type"] == "action")


def _single_action_document(
    *,
    app: str,
    action: str,
    parameters: dict[str, Any],
    asset: str = "asset_one",
    mode: str = "air_gapped",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "single-action",
        "name": "Single action",
        "description": "Synthetic validator fixture.",
        "entrypoint": "start",
        "nodes": [
            {"id": "start", "type": "start", "next": "run"},
            {
                "id": "run",
                "type": "action",
                "app": app,
                "action": action,
                "asset": {"kind": "asset", "name": asset},
                "parameters": parameters,
                "on_success": "complete",
                "on_failure": "failed",
            },
            {"id": "complete", "type": "end", "outcome": "success"},
            {"id": "failed", "type": "end", "outcome": "failure"},
        ],
        "metadata": {
            "capability_index_version": "single-v1",
            "operating_mode": mode,
        },
    }


def _single_action_index(
    *,
    app: str,
    action: ActionCapability,
    asset: bool = True,
) -> CapabilityIndex:
    return CapabilityIndex(
        index_version="single-v1",
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
            if asset
            else []
        ),
        permissions_status="verified",
        permission_principal="test",
        action_permissions={f"{app}:{action.name}": "allowed"},
        custom_lists_status="verified",
        playbooks_status="verified",
    )


def test_fully_evidenced_fixture_has_no_false_positive():
    report = preflight(
        qualified_smoke_ir(),
        qualified_smoke_index(),
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    assert report.status == "ok"
    assert report.gaps == ()
    assert report.index_age_seconds == 0


def test_index_state_rules():
    index = qualified_smoke_index()
    index.harvest_status = "partial"
    index.harvest_errors = ["asset endpoint denied"]
    index.built_at = "2026-07-20T16:00:00+00:00"
    report = preflight(
        qualified_smoke_ir(),
        index,
        evaluated_at=FIXTURE_EVALUATED_AT,
    )
    assert {"INDEX_HARVEST_DEGRADED", "INDEX_STALE"} <= _ids(report)
    assert report.status == "degraded"

    missing = qualified_smoke_index()
    missing.built_at = ""
    assert "INDEX_TIMESTAMP_MISSING" in _ids(
        preflight(
            qualified_smoke_ir(),
            missing,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )

    mismatch_doc = qualified_smoke_document()
    mismatch_doc["metadata"]["capability_index_version"] = "old-index"
    assert "CAPABILITY_INDEX_VERSION_MISMATCH" in _ids(_run(mismatch_doc))


def test_action_resolution_evidence_rules():
    unknown_app = qualified_smoke_document()
    _action(unknown_app)["app"] = "not_installed"
    assert "ACTION_APP_UNKNOWN" in _ids(_run(unknown_app))

    unknown_action = qualified_smoke_document()
    _action(unknown_action)["action"] = "invented action"
    assert "ACTION_NOT_FOUND" in _ids(_run(unknown_action))

    baseline_app = qualified_smoke_index()
    baseline_app.apps["okta"].source = "baseline"
    assert "APP_INSTALLATION_UNVERIFIED" in _ids(
        preflight(
            qualified_smoke_ir(),
            baseline_app,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )

    baseline_action = qualified_smoke_index()
    baseline_action.apps["okta"].actions[0].source = "baseline"
    assert "ACTION_INSTALLATION_UNVERIFIED" in _ids(
        preflight(
            qualified_smoke_ir(),
            baseline_action,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )


def test_asset_rules():
    unbound = qualified_smoke_document()
    _action(unbound)["asset"] = {"kind": "asset_unbound"}
    report = _run(unbound)
    assert "ASSET_UNBOUND" in _ids(report)
    gap = next(gap for gap in report.gaps if gap.id == "ASSET_UNBOUND")
    assert gap.detail["candidate_assets"] == ["okta_lab"]
    assert gap.detail["required_config_keys"] == ["base_url", "token"]

    missing = qualified_smoke_document()
    _action(missing)["asset"]["name"] = "missing"
    assert "ASSET_MISSING" in _ids(_run(missing))

    mismatch_index = qualified_smoke_index()
    mismatch_index.assets[0].app = "servicenow"
    assert "ASSET_APP_MISMATCH" in _ids(
        preflight(
            qualified_smoke_ir(),
            mismatch_index,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )

    unhealthy = qualified_smoke_index()
    unhealthy.assets[0].configured = False
    unhealthy.assets[0].healthy = False
    ids = _ids(
        preflight(
            qualified_smoke_ir(),
            unhealthy,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )
    assert {"ASSET_NOT_CONFIGURED", "ASSET_UNHEALTHY"} <= ids


def test_parameter_rules():
    missing = qualified_smoke_document()
    _action(missing)["parameters"] = {}
    assert "PARAMETER_REQUIRED" in _ids(_run(missing))

    unknown = qualified_smoke_document()
    _action(unknown)["parameters"]["invented"] = {
        "kind": "literal",
        "value": "x",
    }
    assert "PARAMETER_UNKNOWN" in _ids(_run(unknown))

    wrong_literal = qualified_smoke_document()
    _action(wrong_literal)["parameters"]["username"] = {
        "kind": "literal",
        "value": 7,
    }
    ids = _ids(_run(wrong_literal))
    assert {"PARAMETER_TYPE_MISMATCH", "CONTAINS_MISMATCH"} <= ids

    wrong_contains = qualified_smoke_document()
    _action(wrong_contains)["parameters"]["username"]["path"] = [
        "cef",
        "sourceAddress",
    ]
    assert "CONTAINS_MISMATCH" in _ids(_run(wrong_contains))


def test_datapath_rules():
    unknown_cef = qualified_smoke_document()
    _action(unknown_cef)["parameters"]["username"]["path"] = [
        "cef",
        "madeUpField",
    ]
    assert "DATAPATH_UNKNOWN" in _ids(_run(unknown_cef))

    playbook_input = qualified_smoke_document()
    _action(playbook_input)["parameters"]["username"] = {
        "kind": "datapath",
        "scope": "playbook_input",
        "path": ["username"],
    }
    assert "PLAYBOOK_INPUT_UNDECLARED" in _ids(_run(playbook_input))

    wrong_output = qualified_smoke_document()
    decision = next(
        node for node in wrong_output["nodes"] if node["type"] == "decision"
    )
    decision["condition"]["value"]["path"] = ["data", "*", "invented"]
    assert "OUTPUT_DATAPATH_UNKNOWN" in _ids(_run(wrong_output))


def test_permission_rules():
    unverified = qualified_smoke_index()
    unverified.permissions_status = "unavailable"
    unverified.action_permissions = {}
    assert "PERMISSION_UNVERIFIED" in _ids(
        preflight(
            qualified_smoke_ir(),
            unverified,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )

    denied = qualified_smoke_index()
    denied.action_permissions["okta:get user"] = "denied"
    assert "PERMISSION_DENIED" in _ids(
        preflight(
            qualified_smoke_ir(),
            denied,
            evaluated_at=FIXTURE_EVALUATED_AT,
        )
    )


def test_egress_rules_and_substitution():
    action = ActionCapability(
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
    document = _single_action_document(
        app="virustotalv3",
        action="file reputation",
        parameters={
            "hash": {
                "kind": "literal",
                "value": "a" * 64,
            }
        },
    )
    report = _run(
        document,
        _single_action_index(app="virustotalv3", action=action),
    )
    assert "EGRESS_REQUIRED" in _ids(report)
    assert len(report.substitutions) == 1
    assert report.substitutions[0].replacement_app == "phantom"
    assert report.substitutions[0].automatic is False

    action.requires_egress = "unknown"
    document["metadata"]["operating_mode"] = "connected"
    report = _run(
        document,
        _single_action_index(app="virustotalv3", action=action),
    )
    assert "EGRESS_UNKNOWN" in _ids(report)
    assert report.status == "degraded"


def test_referenced_objects_and_builtin_compiler_policy():
    action = ActionCapability(
        name="add list",
        app="phantom",
        parameters=[
            ActionParameter(name="list_name", data_type="string", required=True),
            ActionParameter(name="value", data_type="string", required=True),
        ],
        requires_egress="false",
        source="discovered",
    )
    document = _single_action_document(
        app="phantom",
        action="add list",
        parameters={
            "list_name": {"kind": "literal", "value": "local_threat_intel"},
            "value": {"kind": "literal", "value": "example.test"},
        },
    )
    index = _single_action_index(app="phantom", action=action, asset=False)
    report = _run(document, index)
    assert {
        "REFERENCED_OBJECT_MISSING",
        "BUILTIN_ACTION_COMPILER_UNQUALIFIED",
    } <= _ids(report)

    index.custom_lists_status = "unavailable"
    assert "OBJECT_INVENTORY_UNAVAILABLE" in _ids(_run(document, index))


def test_all_join_is_blocked_until_ir_has_fork_semantics():
    document = qualified_smoke_document()
    join = next(node for node in document["nodes"] if node["type"] == "join")
    join["strategy"] = "all"
    assert "ALL_JOIN_UNREACHABLE" in _ids(_run(document))


def test_evaluated_at_must_be_explicit_and_timezone_aware():
    try:
        preflight(
            qualified_smoke_ir(),
            qualified_smoke_index(),
            evaluated_at="2026-07-28T16:00:00",
        )
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("naive evaluated_at timestamp was accepted")
