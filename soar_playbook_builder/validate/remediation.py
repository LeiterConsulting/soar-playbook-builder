"""Static, model-free remediation knowledge for deterministic gap IDs."""

from __future__ import annotations

from typing import Any

from capability.schema import CapabilityIndex

from .report import ArtifactNeeded, Remediation


def _app_artifact(
    detail: dict[str, Any],
    index: CapabilityIndex,
) -> tuple[ArtifactNeeded, ...]:
    app_name = str(detail.get("app") or "")
    app = index.apps.get(app_name)
    version = app.version if app else str(detail.get("version") or "")
    return (
        ArtifactNeeded(
            type="app_package",
            name=app_name,
            version=version,
            splunkbase_id="",
            transfer_note=(
                "Obtain the approved app package on a connected staging system, "
                "verify its vendor checksum/signature, scan it, then transfer it "
                "through the organization's offline media process."
            ),
        ),
    )


def remediation_for(
    gap_id: str,
    detail: dict[str, Any],
    index: CapabilityIndex,
) -> Remediation:
    """Return literal steps only; unknown IDs receive a safe generic sequence."""
    app = str(detail.get("app") or "")
    action = str(detail.get("action") or "")
    node = str(detail.get("node") or "")
    mappings: dict[str, tuple[str, ...]] = {
        "ACTION_APP_UNKNOWN": (
            f"Install an approved app that exposes `{app}` on the target SOAR instance.",
            "Rebuild the capability index locally.",
            f"Re-run preflight for node `{node}` and confirm the app is discovered.",
        ),
        "APP_INSTALLATION_UNVERIFIED": (
            f"Confirm `{app}` is installed on the target SOAR instance.",
            "Rebuild the capability index with app-detail access.",
            f"Require discovered evidence before enabling node `{node}`.",
        ),
        "ACTION_NOT_FOUND": (
            f"Open the installed `{app}` app action catalog.",
            f"Select an exact discovered action instead of `{action}`.",
            "Regenerate the IR and re-run preflight.",
        ),
        "ACTION_INSTALLATION_UNVERIFIED": (
            f"Confirm `{action}` exists in the installed `{app}` version.",
            "Rebuild the capability index and require the action source to be discovered or merged.",
            "Re-run preflight without changing the warning into an allow decision.",
        ),
        "ASSET_UNBOUND": (
            f"Create or select a healthy `{app}` asset.",
            f"Replace `asset_unbound` on node `{node}` with the exact asset name.",
            "Run the asset connectivity test, rebuild the index, and re-run preflight.",
        ),
        "ASSET_MISSING": (
            f"Create the named asset for `{app}` or bind node `{node}` to a discovered asset.",
            "Configure every required connector field shown in the app package.",
            "Pass the asset connectivity test and rebuild the capability index.",
        ),
        "ASSET_APP_MISMATCH": (
            f"Bind node `{node}` to an asset owned by `{app}`.",
            "Do not reuse an asset merely because its display name is similar.",
            "Rebuild the index and re-run preflight.",
        ),
        "ASSET_NOT_CONFIGURED": (
            "Complete the asset configuration in SOAR.",
            "Save it, run Test Connectivity, and rebuild the capability index.",
            "Re-run preflight.",
        ),
        "ASSET_UNHEALTHY": (
            "Open the asset and inspect its most recent connectivity error.",
            "Repair credentials, certificate trust, routing, or service health offline as applicable.",
            "Require a healthy index record before import.",
        ),
        "PARAMETER_REQUIRED": (
            f"Bind every required parameter listed for `{app}:{action}` on node `{node}`.",
            "Use a literal, a verified SOAR datapath, or a verified prior-node output.",
            "Re-run preflight.",
        ),
        "PARAMETER_UNKNOWN": (
            f"Remove or rename the unsupported parameter on node `{node}`.",
            f"Use only parameters discovered for `{app}:{action}`.",
            "Rebuild the IR and re-run preflight.",
        ),
        "PARAMETER_TYPE_MISMATCH": (
            f"Change the binding on node `{node}` to the discovered parameter data type.",
            "Do not coerce values with free-form Python.",
            "Re-run preflight.",
        ),
        "CONTAINS_MISMATCH": (
            f"Choose a producer whose `contains` type matches the consumer on node `{node}`.",
            "If the local app metadata is wrong, correct the app definition and rebuild the index.",
            "Re-run preflight.",
        ),
        "CONTAINS_UNVERIFIED": (
            f"Harvest producer output `contains` metadata used by node `{node}`.",
            "Require a compatible producer type or replace the binding.",
            "Re-run preflight without treating unknown metadata as compatible.",
        ),
        "DATAPATH_UNKNOWN": (
            f"Replace the unresolved datapath on node `{node}` with a field from the local index.",
            "Rebuild the capability index if the field was recently added.",
            "Re-run preflight.",
        ),
        "DATAPATH_UNVERIFIED": (
            f"Inventory the dynamic container field referenced by node `{node}`.",
            "Confirm its exact name and value type on the target SOAR instance.",
            "Rebuild the index and re-run preflight.",
        ),
        "DESTRUCTIVE_ACTION_REVIEW_REQUIRED": (
            f"Place a prompt node upstream of destructive node `{node}`.",
            "Route the prompt success edge to the destructive action and every rejection/timeout edge to a non-destructive end path.",
            "Re-run preflight and review the exact target, action, asset, and parameters before import.",
        ),
        "OUTPUT_DATAPATH_UNKNOWN": (
            f"Choose an output declared by the exact installed action feeding node `{node}`.",
            "Do not infer an output from another app version.",
            "Re-run preflight.",
        ),
        "PLAYBOOK_INPUT_UNDECLARED": (
            "Define a typed input specification in a future supported IR version.",
            "Until then, replace the input with a verified artifact/container/prior-output binding.",
            "Re-run preflight.",
        ),
        "PERMISSION_DENIED": (
            f"Grant the least-privileged executing principal permission for `{app}:{action}` or remove node `{node}`.",
            "Rebuild the capability index as that principal.",
            "Require an explicit allowed result before import.",
        ),
        "PERMISSION_UNVERIFIED": (
            f"Evaluate `{app}:{action}` using the same principal that will import/run the playbook.",
            "Harvest role and action permission evidence locally.",
            "Re-run preflight; never infer permission from a browser header.",
        ),
        "EGRESS_REQUIRED": (
            f"Replace `{app}:{action}` with the listed offline substitution or approve a controlled egress exception.",
            "Bind the replacement action and re-run capability discovery.",
            "Re-run preflight in the intended operating mode.",
        ),
        "EGRESS_UNKNOWN": (
            f"Classify the network behavior of `{app}:{action}` from local app documentation and testing.",
            "Record the action as true or false in the reviewed egress catalog.",
            "Rebuild the index and re-run preflight.",
        ),
        "REFERENCED_OBJECT_MISSING": (
            "Create the referenced object with the exact case-sensitive name or change the literal binding.",
            "Rebuild the local object inventory.",
            "Re-run preflight.",
        ),
        "OBJECT_INVENTORY_UNAVAILABLE": (
            "Harvest the required custom-list or playbook inventory from the target SOAR instance.",
            "Require verified inventory evidence before import.",
            "Re-run preflight.",
        ),
        "ALL_JOIN_UNREACHABLE": (
            "Change the join to `any` only if mutually exclusive branch semantics are intended.",
            "Otherwise redesign the IR with a supported explicit fork/parallel construct.",
            "Re-run preflight; do not import the unreachable all-join.",
        ),
        "CAPABILITY_INDEX_VERSION_MISMATCH": (
            "Regenerate or rebind the IR against the currently loaded capability index.",
            "Do not overwrite the recorded index version manually.",
            "Re-run preflight and compile from the accepted IR.",
        ),
        "INDEX_TIMESTAMP_MISSING": (
            "Rebuild the capability index so it records a UTC build timestamp.",
            "Verify the persisted checksum and last-known-good state.",
            "Re-run preflight.",
        ),
        "INDEX_STALE": (
            "Rebuild the capability index from the target SOAR instance.",
            "Review harvest warnings and preserve the last-known-good index if refresh fails.",
            "Re-run preflight.",
        ),
        "INDEX_HARVEST_DEGRADED": (
            "Review every capability harvest error.",
            "Restore the unavailable local REST permissions/endpoints.",
            "Rebuild the index; do not treat baseline data as live evidence.",
        ),
        "BUILTIN_ACTION_COMPILER_UNQUALIFIED": (
            f"Do not compile `{app}:{action}` through the generic asset action renderer.",
            "Add and live-qualify an explicit SOAR-native API mapping for this action.",
            "Re-run compiler and runtime qualification tests before enabling import.",
        ),
        "MODEL_OUTPUT_INVALID": (
            "Keep the model output outside the trusted compiler path.",
            "Review the bounded schema issue codes and correct the generation prompt or model configuration.",
            "Retry generation; never convert invalid model text directly into Python or a SOAR artifact.",
        ),
        "MODEL_PROVIDER_FAILED": (
            "Confirm the configured model endpoint, certificate trust, authentication, and resource availability.",
            "Run the local provider capability probe and keep schema or grammar constraints enabled when supported.",
            "Retry generation after the provider is healthy; deterministic compilation remains disabled for this result.",
        ),
        "MODEL_REPAIR_EXHAUSTED": (
            "Review the final structured validation gap codes without trusting the discarded model text.",
            "Correct the request, local capability evidence, prompt, or model selection.",
            "Start a new bounded generation run; do not extend the repair loop indefinitely.",
        ),
    }
    steps = mappings.get(
        gap_id,
        (
            "Review the structured gap detail.",
            "Correct the IR or rebuild the local capability evidence.",
            "Re-run deterministic preflight.",
        ),
    )
    artifacts = (
        _app_artifact(detail, index)
        if gap_id in ("ACTION_APP_UNKNOWN", "APP_INSTALLATION_UNVERIFIED")
        else ()
    )
    return Remediation(
        offline_capable=True,
        steps=steps,
        artifacts_needed=artifacts,
    )
