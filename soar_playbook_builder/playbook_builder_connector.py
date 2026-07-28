"""
SOAR Playbook Builder sidecar — guided build, preview, and MCP bridge proxy.

REST routes (after /rest/handler/<directory>/<asset>/):
  GET  chat           — playbook builder sidecar UI + JSON API
  GET  widget         — compact poll widget
  POST poll_playbook  — VPE live-sync fingerprint
  GET  list_lessons   — curriculum index
  POST proxy_chat     — proxy chat to MCP bridge
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

import phantom.app as phantom
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector
from soar_rest import build_phantom_rest_url

from builder_helpers import (
    analyze_playbook,
    builder_steps_payload,
    parse_builder_action,
    preview_blocks_from_source,
    scaffold_pattern,
)
from capability.index import build_index, index_status
from preview_visual import attach_visual_preview, soar_playbook_links
from sidecar_url import append_query as _append_query
from sidecar_url import build_sidecar_query_params as _build_sidecar_query_params
from troubleshooting_catalog import attach_troubleshooting, troubleshooting_api_payload

APP_SUCCESS = phantom.APP_SUCCESS
APP_ERROR = phantom.APP_ERROR

_SNAPSHOTS = {}
_DRAFT_CACHE: dict[str, dict[str, str]] = {}

LESSON_INDEX = []  # legacy; use tutor_local.list_lessons_payload()


def _apps_from_rest_response(resp):
    """Normalize SOAR /rest/app response to a list of app dicts."""
    if isinstance(resp, list):
        return [a for a in resp if isinstance(a, dict)]
    if isinstance(resp, dict):
        data = resp.get("data") or resp.get("apps") or []
        if isinstance(data, list):
            return [a for a in data if isinstance(a, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _handler_directory_slug(app_uuid=None):
    """Return SOAR REST handler directory (e.g. soarplaybookbuilder_<uuid>).

    SOAR registers handlers using the installed app's ``directory`` field, which
    is derived from the display name — not ``package_name`` (soar_playbook_builder).
    """
    app_uuid = app_uuid or phantom.get_app_id()
    try:
        url = build_phantom_rest_url("app")
        ok, resp = phantom.rest(url, params={"page_size": 500})
        for app in _apps_from_rest_response(resp if ok else None):
            if app.get("appid") == app_uuid and app.get("directory"):
                return app["directory"]
    except Exception:  # noqa: BLE001
        pass

    app_json = {}
    try:
        app_json = phantom.get_app_json() or {}
    except Exception:  # noqa: BLE001
        pass

    label = app_json.get("name") or app_json.get("product_name") or "soarplaybookbuilder"
    slug = re.sub(r"[^a-z0-9]", "", label.lower())
    directory = f"{slug}_{app_uuid}"
    # Prefer live directory from REST (handles renames across installs)
    return directory


class PlaybookBuilderConnector(BaseConnector):
    """Playbook Builder connector — MCP bridge test and sidecar URL."""

    def initialize(self):
        self._mcp_bridge_url = self.get_config().get(
            "mcp_bridge_url", "http://localhost:8003/agent"
        ).rstrip("/")
        self._ai_instructions = self.get_config().get(
            "ai_instructions",
            "Describe playbooks in plain language — preview, validate, and import into SOAR",
        )
        return APP_SUCCESS

    def finalize(self):
        return APP_SUCCESS

    def _sidecar_base_url(self):
        """Best-effort REST handler base for this asset."""
        try:
            asset = self.get_asset_id()
            directory = _handler_directory_slug(self.get_app_id())
            base = phantom.get_base_url().rstrip("/")
            return f"{base}/rest/handler/{directory}/{asset}"
        except Exception:  # noqa: BLE001
            return "Configure asset and use Apps → asset settings for handler URL"

    def _handle_test_connectivity(self, param, action_result):
        self.save_progress("Testing MCP bridge")

        health_url = f"{self._mcp_bridge_url}/../health"
        if self._mcp_bridge_url.endswith("/agent"):
            health_url = self._mcp_bridge_url.rsplit("/agent", 1)[0] + "/agent/health"

        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
                body = resp.read().decode("utf-8", errors="replace")
            sidecar = _append_query(f"{self._sidecar_base_url()}/chat", _build_sidecar_query_params(param))
            action_result.update_data(
                [
                    {
                        "bridge_health": body[:500],
                        "sidecar_url": sidecar,
                        "mcp_bridge_url": self._mcp_bridge_url,
                    }
                ]
            )
            return action_result.set_status(
                APP_SUCCESS,
                f"MCP bridge reachable. Sidecar: {sidecar}",
            )
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(
                APP_ERROR,
                f"MCP bridge unreachable at {self._mcp_bridge_url}: {exc}",
            )

    def _handle_get_sidecar_url(self, param, action_result):
        base = self._sidecar_base_url()
        url = _append_query(f"{base}/chat", _build_sidecar_query_params(param))
        action_result.update_data([{"sidecar_url": url}])
        hint = "Pass container_id to link a SOAR case (Run on this case)."
        if param.get("container_id"):
            hint = f"Sidecar linked to case {param.get('container_id')}."
        return action_result.set_status(APP_SUCCESS, f"{url} — {hint}")

    def handle_action(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        action = self.get_action_identifier()

        if action == "test_connectivity":
            return self._handle_test_connectivity(param, action_result)
        if action == "get_sidecar_url":
            return self._handle_get_sidecar_url(param, action_result)
        if action == "rebuild_capability_index":
            return self._handle_rebuild_capability_index(param, action_result)
        if action == "capability_index_status":
            return self._handle_capability_index_status(param, action_result)
        if action == "export_asset_config":
            return self._handle_export_asset_config(param, action_result)
        if action == "import_asset_config":
            return self._handle_import_asset_config(param, action_result)
        if action == "run_self_test":
            return self._handle_run_self_test(param, action_result)

        return action_result.set_status(APP_ERROR, f"Unknown action: {action}")

    def _handle_rebuild_capability_index(self, param, action_result):
        self.save_progress("Rebuilding capability index from local SOAR REST")
        try:
            index, saved = build_index(persist=True)
            status = index_status()
            action_result.update_data(
                [
                    {
                        "index_version": index.index_version,
                        "built_at": index.built_at,
                        "harvest_status": index.harvest_status,
                        "app_count": status.get("app_count"),
                        "action_count": status.get("action_count"),
                        "asset_count": status.get("asset_count"),
                        "index_path": str(saved) if saved else status.get("path"),
                        "harvest_errors": index.harvest_errors[:10],
                    }
                ]
            )
            msg = (
                f"Capability index rebuilt — {status.get('app_count')} apps, "
                f"{status.get('action_count')} actions, status={index.harvest_status}"
            )
            if index.harvest_errors:
                msg += f" ({len(index.harvest_errors)} harvest warnings)"
            return action_result.set_status(APP_SUCCESS, msg)
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(APP_ERROR, f"Capability index rebuild failed: {exc}")

    def _handle_capability_index_status(self, param, action_result):
        self.save_progress("Reading capability index status")
        try:
            status = index_status()
            action_result.update_data([status])
            if status.get("loaded"):
                return action_result.set_status(
                    APP_SUCCESS,
                    f"Index {status.get('index_version')} — "
                    f"{status.get('app_count')} apps, stale={status.get('stale')}",
                )
            return action_result.set_status(
                APP_SUCCESS,
                "No persisted index — baseline only until rebuild capability index runs",
            )
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(APP_ERROR, f"Capability index status failed: {exc}")

    def _handle_export_asset_config(self, param, action_result):
        self.save_progress("Exporting Playbook Builder asset configuration")
        try:
            from asset_config import export_asset_config_payload

            include_secrets = str(param.get("include_secrets") or "").lower() in ("1", "true", "yes")
            cfg = dict(self.get_config() or {})
            sidecar = _append_query(f"{self._sidecar_base_url()}/chat", _build_sidecar_query_params(param))
            payload = export_asset_config_payload(cfg, include_secrets=include_secrets, sidecar_url=sidecar)
            action_result.update_data([payload])
            return action_result.set_status(APP_SUCCESS, payload.get("message", "Exported"))
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(APP_ERROR, f"Export failed: {exc}")

    def _handle_import_asset_config(self, param, action_result):
        self.save_progress("Importing Playbook Builder asset configuration")
        try:
            from asset_config import import_asset_config_payload

            raw = param.get("config_json") or param.get("configuration_json")
            confirm = str(param.get("confirm") or "").lower() in ("1", "true", "yes")
            cfg = dict(self.get_config() or {})
            payload = import_asset_config_payload(
                None,
                cfg,
                config_json=raw,
                confirm=confirm,
                asset_name_hint=str(param.get("asset_name") or self.get_asset_name() or ""),
            )
            action_result.update_data([payload])
            if payload.get("status") == "error":
                return action_result.set_status(APP_ERROR, payload.get("error", "Import failed"))
            if payload.get("needs_confirm"):
                return action_result.set_status(APP_SUCCESS, payload.get("message", "Confirm import"))
            return action_result.set_status(APP_SUCCESS, payload.get("message", "Imported"))
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(APP_ERROR, f"Import failed: {exc}")

    def _handle_run_self_test(self, param, action_result):
        self.save_progress("Running Playbook Builder self-test")
        try:
            from self_test import run_self_test

            cfg = dict(self.get_config() or {})
            payload = run_self_test(cfg, bridge_probe=lambda: _probe_mcp_bridge(self._mcp_bridge_url))
            action_result.update_data([payload])
            if payload.get("blocking"):
                return action_result.set_status(APP_SUCCESS, payload.get("message", "Self-test needs attention"))
            return action_result.set_status(APP_SUCCESS, payload.get("message", "Self-test passed"))
        except Exception as exc:  # noqa: BLE001
            return action_result.set_status(APP_ERROR, f"Self-test failed: {exc}")


def _render_template(name: str, **replacements: str) -> str:
    base = os.path.join(os.path.dirname(__file__), "widgets", name)
    try:
        with open(base, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return f"<html><body>Missing template: {name}</body></html>"
    for key, val in replacements.items():
        text = text.replace("{{" + key + "}}", val or "")
    return text


def _fingerprint_playbook(playbook_id):
    url = build_phantom_rest_url(f"playbook/{playbook_id}")
    success, response = phantom.rest(url)
    if not success:
        return {"sha256": None, "error": str(response)}

    data = response if isinstance(response, dict) else {}
    if isinstance(response, list) and response:
        data = response[0]

    blob = json.dumps(
        {
            "id": data.get("id"),
            "name": data.get("name"),
            "version": data.get("version"),
            "hash": data.get("hash"),
        },
        sort_keys=True,
    )
    return {
        "playbook_id": playbook_id,
        "name": data.get("name"),
        "version": data.get("version"),
        "sha256": hashlib.sha256(blob.encode()).hexdigest(),
    }


def handle_poll_playbook(param):
    playbook_id = int(param.get("playbook_id") or 0)
    if not playbook_id:
        return {"status": "error", "message": "playbook_id required"}

    reset = bool(param.get("reset_snapshot"))
    fp = _fingerprint_playbook(playbook_id)
    key = str(playbook_id)
    prev = _SNAPSHOTS.get(key)

    if reset or not prev:
        _SNAPSHOTS[key] = fp
        return {
            "status": "success",
            "changed": False,
            "message": "Snapshot stored. Poll again after import.",
            "fingerprint": fp,
        }

    changed = prev.get("sha256") != fp.get("sha256")
    _SNAPSHOTS[key] = fp
    return {
        "status": "success",
        "changed": changed,
        "vpe_action": "Refresh Visual Playbook Editor" if changed else "No change",
        "previous": prev,
        "current": fp,
    }


def handle_list_lessons(_param):
    from tutor_local import list_lessons_payload

    return list_lessons_payload()


def _chat_context_from_request(request):
    """Build tutor context dict from GET query params."""
    ctx = {"source": "soar"}
    for key in ("playbook_id", "container_id", "event_id"):
        raw = request.GET.get(key)
        if raw:
            try:
                ctx[key] = int(raw)
            except (TypeError, ValueError):
                ctx[key] = raw
    for key in ("rule_name", "investigation_id", "pattern"):
        raw = request.GET.get(key)
        if raw:
            ctx[key if key != "pattern" else "current_pattern"] = raw
    return ctx


def _is_python_source(source) -> bool:
    return isinstance(source, str) and "def on_start" in source


def _has_builder_payload(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    if _is_python_source(payload.get("source")):
        return True
    if payload.get("preview"):
        return True
    if payload.get("content"):
        return True
    return False


def _normalize_bridge_response(data):
    """Pass scaffold-shaped bridge payloads through for the sidecar preview panel."""
    if not isinstance(data, dict):
        return data
    if data.get("status") == "error":
        return data
    inner = data
    if data.get("status") == "success" and data.get("source") and "preview" in data:
        inner = dict(data)
    elif isinstance(data.get("result"), dict) and data["result"].get("source"):
        inner = {**data, **data["result"]}
    return inner


def _soar_base_url(request):
    """SOAR origin (scheme + host) for deep links to Playbooks / VPE."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(request.build_absolute_uri("/"))
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:  # noqa: BLE001
        return ""


def _draft_cache_key(request):
    """Draft cache is independent of ?playbook_id= (that param is legacy context only)."""
    return request.GET.get("draft_key") or "builder"


def _clean_playbook_name(name: str) -> str:
    return re.sub(r"\s*\((offline|stub)\)\s*$", "", name or "", flags=re.IGNORECASE).strip()


def _cache_draft_from_request(request, payload):
    if not isinstance(payload, dict) or not payload.get("source"):
        return
    name = _clean_playbook_name(
        payload.get("pattern_label")
        or payload.get("playbook_name")
        or "NL Draft Playbook"
    )
    key = _draft_cache_key(request)
    entry = _DRAFT_CACHE.setdefault(key, {})
    entry.update(
        {
            "source": payload["source"],
            "name": name,
            "pattern": payload.get("pattern") or "",
        }
    )


def _sync_draft_to_soar(request, payload):
    """Auto-import NL draft so Open Playbook / VPE target the built workflow."""
    if payload.get("status") == "error" or not payload.get("source"):
        return payload
    if payload.get("playbook_id"):
        return payload

    try:
        key = _draft_cache_key(request)
        source_hash = hashlib.sha256(payload["source"].encode()).hexdigest()
        cached = _DRAFT_CACHE.get(key, {})
        if cached.get("imported_hash") == source_hash and cached.get("imported_playbook_id"):
            payload["playbook_id"] = cached["imported_playbook_id"]
            payload["playbook_name"] = cached.get("imported_playbook_name") or cached.get("name")
            payload["auto_imported"] = True
            return payload

        from draft_import import import_nl_draft

        name = cached.get("name") or _clean_playbook_name(payload.get("pattern_label") or "NL Draft Playbook")
        imported = import_nl_draft(
            payload["source"],
            name,
            cached.get("pattern") or payload.get("pattern") or None,
        )
        if imported.get("status") != "success" or not imported.get("playbook_id"):
            payload["import_error"] = imported.get("error", "Auto-import failed")
            if imported.get("import_attempts"):
                payload["import_error"] += "\n" + "\n".join(imported["import_attempts"])
            return payload

        pid = imported["playbook_id"]
        cached["imported_playbook_id"] = pid
        cached["imported_hash"] = source_hash
        cached["imported_playbook_name"] = name
        payload["playbook_id"] = pid
        payload["playbook_name"] = name
        payload["auto_imported"] = True
        note = f"\n\n_Synced to SOAR as **{name}** (id **{pid}**). Open Visual Editor opens this playbook._"
        if payload.get("content"):
            if "Synced to SOAR" not in payload["content"]:
                payload["content"] = str(payload["content"]) + note
        else:
            payload["content"] = imported.get("content") or note.strip()
    except Exception as exc:  # noqa: BLE001
        payload["import_error"] = f"Auto-import failed: {exc}"
    return payload


def _enrich_builder_payload(request, payload, *, auto_import=False):
    if not isinstance(payload, dict) or payload.get("status") == "error":
        return payload
    base = _soar_base_url(request)

    if payload.get("source") and _is_python_source(payload.get("source")):
        _cache_draft_from_request(request, payload)
        if auto_import:
            payload = _sync_draft_to_soar(request, payload)
        payload = attach_visual_preview(payload, base_url=base)
        payload["draft_ready"] = True
        try:
            from playbook_readiness import build_readiness_report

            cfg = getattr(request, "_pb_config", {}) or {}
            linked = payload.get("playbook_id") or request.GET.get("playbook_id")
            payload["readiness"] = build_readiness_report(
                payload.get("source") or "",
                request,
                cfg=cfg,
                linked_playbook_id=linked,
            )
            if payload["readiness"].get("asset_preflight"):
                payload["asset_preflight"] = payload["readiness"]["asset_preflight"]
        except Exception:  # noqa: BLE001
            pass
    elif payload.get("content") and not payload.get("source"):
        payload["draft_ready"] = False
    elif request.GET.get("playbook_id") and request.GET.get("action") == "preview":
        pb = request.GET.get("playbook_id")
        payload.setdefault("playbook_id", pb)
        payload["soar_links"] = soar_playbook_links(base, pb)

    if payload.get("playbook_id") and base:
        payload["soar_links"] = soar_playbook_links(
            base,
            payload["playbook_id"],
            playbook_name=payload.get("playbook_name"),
            playbook_slug=payload.get("playbook_slug"),
            playbook_display_name=payload.get("playbook_display_name")
            or payload.get("pattern_label"),
            playbook_search=payload.get("playbook_search"),
            playbook_record=payload.get("playbook_record")
            if isinstance(payload.get("playbook_record"), dict)
            else None,
        )
    return payload


def _finalize_chat_payload(payload: Any) -> dict[str, Any]:
    """Attach troubleshooting hints to error and blocked-import payloads."""
    if not isinstance(payload, dict):
        return attach_troubleshooting({"status": "error", "error": str(payload)})
    return attach_troubleshooting(payload)


def _safe_enrich_builder_payload(request, payload, *, auto_import=False):
    """Enrich preview; never raise — return error payload instead."""
    try:
        enriched = _enrich_builder_payload(request, payload, auto_import=auto_import)
        return _finalize_chat_payload(enriched)
    except Exception as exc:  # noqa: BLE001
        import traceback

        return _finalize_chat_payload(
            {
                "status": "error",
                "error": f"Preview enrichment failed: {exc}",
                "traceback": traceback.format_exc()[-800:],
                "source": (payload or {}).get("source") if isinstance(payload, dict) else None,
            }
        )


def _live_playbook_preview(playbook_id):
    """Fetch playbook metadata from SOAR and return an approximate preview."""
    try:
        pid = int(playbook_id)
    except (TypeError, ValueError):
        return {"status": "error", "error": "Invalid playbook_id"}

    url = build_phantom_rest_url(f"playbook/{pid}")
    ok, resp = phantom.rest(url)
    if not ok:
        return {"status": "error", "error": f"Could not load playbook {pid}: {resp}"}

    data = resp[0] if isinstance(resp, list) and resp else resp
    if not isinstance(data, dict):
        return {"status": "error", "error": f"Unexpected playbook response for {pid}"}

    name = data.get("name") or f"Playbook {pid}"
    preview = [
        {"type": "start", "label": "Start", "detail": name},
        {
            "type": "vpe",
            "label": "Visual Editor",
            "detail": "Graph lives in VPE — import/scaffold then refresh",
        },
        {
            "type": "end",
            "label": "Finish",
            "detail": f"v{data.get('version', '?')} · id {pid}",
        },
    ]
    result = {
        "status": "success",
        "content": (
            f"Loaded playbook **{name}** (id {pid}). "
            "Use scaffold patterns to draft changes, then import and refresh VPE."
        ),
        "preview": preview,
        "playbook": {
            "id": pid,
            "name": name,
            "version": data.get("version"),
            "description": data.get("description"),
        },
        "playbook_id": pid,
    }
    return result


def _validate_pattern(pattern, org_registry=None):
    result = scaffold_pattern(pattern, org_registry=org_registry)
    if result.get("status") != "success":
        return result
    analysis = result["analysis"]
    lines = [f"Validation score: **{analysis['score']}/100**"]
    for finding in analysis.get("findings", []):
        lines.append(f"- [{finding['level']}] {finding['message']}")
    if analysis.get("datapaths"):
        lines.append("Datapaths: " + ", ".join(analysis["datapaths"]))
    result["content"] = "\n".join(lines)
    return result


def _parse_asset_map(raw: Any) -> dict[str, str]:
    from asset_resolver import parse_asset_defaults

    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if v}
    return parse_asset_defaults(raw)


def _handle_import_draft(request, payload=None):
    """Import NL draft — source may come from POST body (preferred) or server cache."""
    payload = payload or {}
    if payload.get("confirm") not in (True, 1, "1", "true"):
        if request.GET.get("confirm") != "1" and str(payload.get("confirm", "")).lower() not in {"1", "true"}:
            return {
                "status": "error",
                "error": "Import requires confirm=1 (use Import to SOAR button).",
            }

    pattern = payload.get("pattern") or request.GET.get("pattern")
    from pattern_catalog import pattern_meta

    org = getattr(request, "_pb_org_registry", None)
    meta = pattern_meta(pattern, org_registry=org) if pattern else {}
    if meta.get("tier") == "destructive" and payload.get("destructive_confirm") not in (
        True,
        1,
        "1",
        "true",
    ):
        if str(payload.get("destructive_confirm", "")).lower() not in {"1", "true"}:
            return {
                "status": "error",
                "error": (
                    "Destructive template import requires destructive_confirm=1. "
                    "This playbook may disable users, block IPs, or quarantine endpoints."
                ),
                "tier": "destructive",
                "requires_destructive_confirm": True,
                "destructive_actions": meta.get("destructive_actions") or [],
            }

    source = (payload.get("source") or request.GET.get("source") or "").strip()
    name = _clean_playbook_name(
        payload.get("name")
        or payload.get("pattern_label")
        or request.GET.get("name")
        or "NL Draft Playbook"
    )

    draft = _DRAFT_CACHE.get(_draft_cache_key(request), {})
    if not source and draft.get("source"):
        source = draft["source"]
    if name == "NL Draft Playbook" and draft.get("name"):
        name = draft["name"]
    if not pattern and draft.get("pattern"):
        pattern = draft.get("pattern")

    if not source:
        return {
            "status": "error",
            "error": "No draft to import. Build or generate a playbook first.",
        }

    _DRAFT_CACHE[_draft_cache_key(request)] = {
        "source": source,
        "name": name,
        "pattern": pattern or "",
    }

    from draft_import import import_nl_draft

    cfg = getattr(request, "_pb_config", {}) or {}
    from asset_resolver import parse_asset_defaults

    asset_defaults = parse_asset_defaults(cfg.get("asset_defaults"))
    asset_map = _parse_asset_map(payload.get("asset_map"))

    imported = import_nl_draft(
        source,
        name,
        pattern or None,
        request=request,
        asset_map=asset_map,
        asset_defaults=asset_defaults,
    )
    if imported.get("status") == "success" and imported.get("playbook_id"):
        key = _draft_cache_key(request)
        cached = _DRAFT_CACHE.setdefault(key, {})
        cached["imported_playbook_id"] = imported["playbook_id"]
        cached["imported_hash"] = hashlib.sha256(source.encode()).hexdigest()
        cached["imported_playbook_name"] = (
            imported.get("playbook_display_name")
            or imported.get("playbook_name")
            or name
        )
        imported["playbook_display_name"] = (
            imported.get("playbook_display_name") or cached["imported_playbook_name"]
        )
        imported["playbook_name"] = cached["imported_playbook_name"]
        imported["draft_ready"] = True
    if imported.get("status") == "success":
        from builder_helpers import analyze_playbook, preview_blocks_from_source

        imported.setdefault("source", source)
        imported["preview"] = preview_blocks_from_source(imported["source"])
        imported["analysis"] = analyze_playbook(imported["source"])
    return imported


def _chat_param(request, post_body, key, default=None):
    """Read chat API param from POST body (preferred) or GET query."""
    if post_body and key in post_body and post_body.get(key) is not None:
        val = post_body.get(key)
        return val if val != "" else default
    return request.GET.get(key, default)


def _handle_chat_api(request, cfg, post_body=None):
    """GET /chat?... or POST {action: chat, message: ...} — builder + tutor API."""
    post_body = post_body or {}
    org = getattr(request, "_pb_org_registry", None)
    action = (_chat_param(request, post_body, "action") or "").strip().lower()

    if action == "links":
        pb = _chat_param(request, post_body, "playbook_id")
        return {
            "status": "success",
            "soar_links": soar_playbook_links(_soar_base_url(request), pb),
            "playbook_id": pb,
        }

    if action == "bridge_status":
        probe = _probe_mcp_bridge(cfg["mcp_bridge_url"])
        if not probe.get("reachable"):
            probe["hint"] = (
                "SOAR must reach the MCP agent bridge from this server — verify "
                f"{probe['health_url']} from the SOAR host (not only from your workstation)."
            )
        return _finalize_chat_payload(probe)

    if action in ("troubleshoot", "list_troubleshooting"):
        q = (
            _chat_param(request, post_body, "q")
            or _chat_param(request, post_body, "query")
            or (getattr(request, "GET", None) or {}).get("q")
            or ""
        )
        return troubleshooting_api_payload(str(q) if q else None)

    if action == "import_draft":
        body = {
            "confirm": _chat_param(request, post_body, "confirm"),
            "destructive_confirm": _chat_param(request, post_body, "destructive_confirm"),
            "source": _chat_param(request, post_body, "source"),
            "name": _chat_param(request, post_body, "name"),
            "pattern": _chat_param(request, post_body, "pattern"),
            "asset_map": _chat_param(request, post_body, "asset_map"),
        }
        return _safe_enrich_builder_payload(
            request, _handle_import_draft(request, body), auto_import=False
        )

    if action == "readiness_check":
        source = (_chat_param(request, post_body, "source") or "").strip()
        draft = _DRAFT_CACHE.get(_draft_cache_key(request), {})
        if not source and draft.get("source"):
            source = draft["source"]
        if not source:
            return _finalize_chat_payload(
                {"status": "error", "error": "No draft to check. Build a playbook first."}
            )
        from playbook_readiness import readiness_payload_from_source

        cfg = getattr(request, "_pb_config", {}) or {}
        asset_map = _parse_asset_map(_chat_param(request, post_body, "asset_map"))
        apply_fixes = _chat_param(request, post_body, "apply_fixes") in (
            True,
            1,
            "1",
            "true",
        )
        payload = readiness_payload_from_source(
            source,
            request,
            cfg=cfg,
            asset_overrides=asset_map,
            linked_playbook_id=_chat_param(request, post_body, "playbook_id"),
            apply_fixes=apply_fixes,
        )
        if payload.get("source"):
            _proxy_cache_draft(
                _chat_context_from_request(request),
                payload["source"],
                cfg["mcp_bridge_url"],
            )
        return _safe_enrich_builder_payload(request, payload, auto_import=False)

    if action == "preflight_import":
        source = (_chat_param(request, post_body, "source") or "").strip()
        pattern = _chat_param(request, post_body, "pattern")
        draft = _DRAFT_CACHE.get(_draft_cache_key(request), {})
        if not source and draft.get("source"):
            source = draft["source"]
        if not pattern and draft.get("pattern"):
            pattern = draft.get("pattern")
        if not source:
            return _finalize_chat_payload(
                {"status": "error", "error": "No draft to check. Build a playbook first."}
            )
        from asset_resolver import build_asset_preflight, parse_asset_defaults, preflight_message

        cfg = getattr(request, "_pb_config", {}) or {}
        asset_map = _parse_asset_map(_chat_param(request, post_body, "asset_map"))
        asset_defaults = parse_asset_defaults(cfg.get("asset_defaults"))
        attempts: list[str] = []
        preflight = build_asset_preflight(
            source,
            request,
            overrides=asset_map,
            defaults=asset_defaults,
            attempts_log=attempts,
        )
        return {
            "status": "success" if preflight.get("ready") else "needs_assets",
            "asset_preflight": preflight,
            "import_attempts": attempts,
            "content": preflight_message(preflight, base_url=_soar_base_url(request)),
            "source": source,
            "pattern": pattern,
            "draft_ready": True,
        }

    if action == "migrate_python39":
        confirm = _chat_param(request, post_body, "confirm")
        if confirm not in (True, 1, "1", "true"):
            from python39_upgrade import migrate_all_legacy_playbooks

            preview = migrate_all_legacy_playbooks(request, dry_run=True)
            preview["hint"] = "Pass confirm=1 to upgrade all Python 2.7 playbooks in local repo."
            return preview
        from python39_upgrade import migrate_all_legacy_playbooks

        slugs_raw = _chat_param(request, post_body, "slugs") or _chat_param(request, post_body, "slug")
        slugs = None
        if slugs_raw:
            if isinstance(slugs_raw, list):
                slugs = [str(s) for s in slugs_raw]
            else:
                slugs = [s.strip() for s in str(slugs_raw).split(",") if s.strip()]
        return migrate_all_legacy_playbooks(request, slugs=slugs, dry_run=False)

    if action == "steps":
        return builder_steps_payload()

    if action == "list_patterns":
        from pattern_catalog import list_patterns_payload

        return list_patterns_payload(org_registry=org)

    if action == "template_manifest":
        from template_manifest import build_template_manifest

        app_ver = (getattr(request, "_pb_config", {}) or {}).get("app_version") or "2.11.0"
        return build_template_manifest(app_version=app_ver)

    if action == "environment_check":
        from environment_check import environment_check_payload

        org = getattr(request, "_pb_org_registry", None)
        cfg = getattr(request, "_pb_config", {}) or {}
        payload = environment_check_payload(request, cfg, org_registry=org)
        payload["default_ui_mode"] = cfg.get("default_ui_mode") or "studio"
        return payload

    if action == "provision_demo_case":
        from demo_provision import provision_demo_case

        raw_sample = _chat_param(request, post_body, "sample_id")
        raw_pattern = _chat_param(request, post_body, "pattern_id") or _chat_param(
            request, post_body, "pattern"
        )
        confirm = _chat_param(request, post_body, "confirm") in (True, 1, "1", "true")
        return provision_demo_case(
            request,
            pattern_id=str(raw_pattern) if raw_pattern else None,
            sample_id=raw_sample,
            sample_cases_json=cfg.get("sample_cases_json"),
            confirm=confirm,
        )

    if action == "apply_environment_fixes":
        from environment_fix import apply_environment_fixes_payload

        confirm = _chat_param(request, post_body, "confirm") in (True, 1, "1", "true")
        asset_hint = str(_chat_param(request, post_body, "asset_name") or "")
        payload = apply_environment_fixes_payload(
            request,
            cfg,
            confirm=confirm,
            asset_name_hint=asset_hint,
        )
        if payload.get("status") == "success" and confirm:
            from environment_check import environment_check_payload

            org = getattr(request, "_pb_org_registry", None)
            payload["environment"] = environment_check_payload(request, cfg, org_registry=org)
        return payload

    if action == "rebuild_capability_index":
        try:
            index, saved = build_index(request=request, persist=True)
            status = index_status()
            return {
                "status": "success",
                "message": (
                    f"Capability index rebuilt — {status.get('app_count')} apps, "
                    f"{status.get('action_count')} actions"
                ),
                "index_version": index.index_version,
                "built_at": index.built_at,
                "harvest_status": index.harvest_status,
                "app_count": status.get("app_count"),
                "action_count": status.get("action_count"),
                "index_path": str(saved) if saved else status.get("path"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}

    if action == "export_asset_config":
        from asset_config import export_asset_config_payload

        include_secrets = _chat_param(request, post_body, "include_secrets") in (True, 1, "1", "true")
        base = ""
        try:
            base = phantom.get_base_url().rstrip("/")
        except Exception:  # noqa: BLE001
            pass
        return export_asset_config_payload(cfg, include_secrets=bool(include_secrets), sidecar_url=base)

    if action == "import_asset_config":
        from asset_config import import_asset_config_payload

        raw = _chat_param(request, post_body, "config_json") or _chat_param(request, post_body, "configuration_json")
        confirm = _chat_param(request, post_body, "confirm") in (True, 1, "1", "true")
        asset_hint = str(_chat_param(request, post_body, "asset_name") or "")
        payload = import_asset_config_payload(
            request,
            cfg,
            config_json=raw,
            confirm=confirm,
            asset_name_hint=asset_hint,
        )
        if payload.get("status") == "success" and confirm:
            from environment_check import environment_check_payload

            org = getattr(request, "_pb_org_registry", None)
            payload["environment"] = environment_check_payload(request, cfg, org_registry=org)
        return payload

    if action == "run_self_test":
        from self_test import run_self_test

        bridge_url = (cfg.get("mcp_bridge_url") or "").strip()
        probe_fn = None
        if bridge_url:
            probe_fn = lambda: _probe_mcp_bridge(bridge_url)  # noqa: E731
        payload = run_self_test(cfg, bridge_probe=probe_fn)
        return payload

    if action == "list_cases":
        from case_catalog import list_cases_payload

        cfg = getattr(request, "_pb_config", {}) or {}
        page_size_raw = _chat_param(request, post_body, "page_size") or "20"
        try:
            page_size = max(1, min(50, int(page_size_raw)))
        except (TypeError, ValueError):
            page_size = 20
        enrich = _chat_param(request, post_body, "enrich_artifacts") not in (
            False,
            0,
            "0",
            "false",
        )
        return list_cases_payload(
            request,
            sample_cases_json=cfg.get("sample_cases_json"),
            page_size=page_size,
            enrich_artifacts=enrich,
        )

    if action == "coach_suggest":
        from coach import coach_suggest_payload

        return coach_suggest_payload(request, cfg, post_body)

    if action == "get_lesson":
        from tutor_local import get_lesson_payload

        slug = _chat_param(request, post_body, "slug") or _chat_param(request, post_body, "lesson")
        return get_lesson_payload(str(slug or ""))

    if action == "list_lessons":
        from tutor_local import list_lessons_payload

        return list_lessons_payload()

    if action == "investigation_context":
        from investigation_context import hydrate_investigation_context, parse_context_ids

        ids = parse_context_ids(request, post_body)
        cfg = getattr(request, "_pb_config", {}) or {}
        return hydrate_investigation_context(
            request,
            es_web_url=cfg.get("es_web_url"),
            sample_cases_json=cfg.get("sample_cases_json"),
            **ids,
        )

    if action == "run_playbook":
        from investigation_context import parse_context_ids
        from playbook_run import run_playbook_on_container

        ids = parse_context_ids(request, post_body)
        raw_pb = _chat_param(request, post_body, "playbook_id")
        raw_cid = ids.get("container_id") or _chat_param(request, post_body, "container_id")
        try:
            playbook_id = int(raw_pb)
            container_id = int(raw_cid)
        except (TypeError, ValueError):
            return {
                "status": "error",
                "error": "run_playbook requires numeric playbook_id and container_id",
            }
        pattern_id = _chat_param(request, post_body, "pattern")
        return run_playbook_on_container(
            request,
            container_id=container_id,
            playbook_id=playbook_id,
            confirm=_chat_param(request, post_body, "confirm"),
            destructive_confirm=_chat_param(request, post_body, "destructive_confirm"),
            pattern_id=pattern_id,
        )

    if action == "scaffold":
        result = scaffold_pattern(
            _chat_param(request, post_body, "pattern", "hello"),
            org_registry=org,
        )
        if result.get("source"):
            _proxy_cache_draft(
                _chat_context_from_request(request),
                result["source"],
                cfg["mcp_bridge_url"],
            )
        return _safe_enrich_builder_payload(request, result, auto_import=False)

    if action == "preview":
        pattern = _chat_param(request, post_body, "pattern")
        if pattern:
            return _safe_enrich_builder_payload(
                request, scaffold_pattern(pattern, org_registry=org), auto_import=False
            )
        pb = _chat_param(request, post_body, "playbook_id")
        if pb:
            return _safe_enrich_builder_payload(
                request, _live_playbook_preview(pb), auto_import=False
            )
        return {"status": "error", "error": "Provide pattern or playbook_id"}

    if action == "validate":
        return _safe_enrich_builder_payload(
            request,
            _validate_pattern(_chat_param(request, post_body, "pattern", "hello"), org_registry=org),
            auto_import=False,
        )

    if _chat_param(request, post_body, "poll"):
        return handle_poll_playbook(
            {"playbook_id": _chat_param(request, post_body, "playbook_id")}
        )

    message = (_chat_param(request, post_body, "message") or "").strip()
    if not message:
        return {"status": "error", "error": "message or action query parameter required"}

    lower = message.lower()
    tutor_lane = (_chat_param(request, post_body, "lane") or "").strip().lower()
    from tutor_local import handle_tutor_message, is_tutor_intent

    if tutor_lane in ("tutor", "explain") or is_tutor_intent(message):
        tutor_payload = handle_tutor_message(message, _chat_context_from_request(request))
        return _finalize_chat_payload(tutor_payload)

    if lower.startswith("review") and "playbook" in lower:
        draft = _DRAFT_CACHE.get(_draft_cache_key(request), {})
        source = (draft.get("source") or "").strip()
        if source:
            from builder_helpers import analyze_playbook

            analysis = analyze_playbook(source)
            findings = analysis.get("findings") or []
            lines = [
                f"**Playbook review** — score {analysis.get('score', '?')}/100",
                "",
            ]
            for f in findings[:8]:
                lines.append(f"- [{f.get('level', 'info')}] {f.get('message', '')}")
            if not findings:
                lines.append("No issues flagged by static analysis.")
            lines.append("")
            lines.append("Switch to **Explain** for lessons, or **Build** to edit and re-import.")
            return _finalize_chat_payload(
                {"status": "success", "content": "\n".join(lines), "coach_lane": "review", "analysis": analysis}
            )

    if lower in ("validate current preview", "validate preview"):
        return _safe_enrich_builder_payload(
            request,
            _validate_pattern(_chat_param(request, post_body, "pattern", "hello"), org_registry=org),
            auto_import=False,
        )

    pattern = parse_builder_action(message)
    if pattern:
        return _safe_enrich_builder_payload(
            request, scaffold_pattern(pattern, org_registry=org), auto_import=False
        )

    # Keyword templates when MCP bridge is offline — custom prompts defer to bridge/LLM.
    from builder_helpers import SCAFFOLDS
    from local_nl_build import is_build_intent, match_pattern, should_defer_to_llm, try_local_build

    bridge_reachable = _probe_mcp_bridge(cfg["mcp_bridge_url"]).get("reachable") is True

    if (
        is_build_intent(message)
        and not bridge_reachable
        and not should_defer_to_llm(message)
    ):
        local_pattern = match_pattern(message, org_registry=org)
        if local_pattern == "panw-block-stub":
            local_pattern = "panw-block-ip"
        if local_pattern and (
            local_pattern in SCAFFOLDS or (org and local_pattern in org.scaffolds)
        ):
            return _safe_enrich_builder_payload(
                request,
                scaffold_pattern(local_pattern, org_registry=org),
                auto_import=False,
            )

    body = {"message": message, "context": _chat_context_from_request(request)}
    bridged = _proxy_chat_to_bridge(body, cfg["mcp_bridge_url"])
    if not _has_builder_payload(bridged):
        bridge_err = bridged.get("error") if bridged.get("status") == "error" else (
            "MCP bridge returned an empty response — verify bridge health from the SOAR server."
        )
        local = try_local_build(message, bridge_error=bridge_err, org_registry=org)
        if local:
            return _safe_enrich_builder_payload(request, local, auto_import=False)
        if bridged.get("status") == "error":
            return _finalize_chat_payload(bridged)
        return _finalize_chat_payload(
            {
                "status": "error",
                "error": bridge_err or "Builder returned no preview or message.",
            }
        )
    return _safe_enrich_builder_payload(request, bridged, auto_import=False)


def _proxy_cache_draft(context, source, mcp_bridge_url):
    """Best-effort seed of bridge draft cache after local scaffold."""
    bridge = mcp_bridge_url.rstrip("/")
    url = f"{bridge}/api/draft"
    payload = json.dumps({"context": context, "source": source}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        pass


def _bridge_health_url(mcp_bridge_url: str) -> str:
    bridge = mcp_bridge_url.rstrip("/")
    if bridge.endswith("/agent"):
        return bridge.rsplit("/agent", 1)[0] + "/agent/health"
    return f"{bridge}/health"


def _probe_mcp_bridge(mcp_bridge_url: str) -> dict:
    """Check reachability from the SOAR app process (same path as chat proxy)."""
    health_url = _bridge_health_url(mcp_bridge_url)
    chat_url = f"{mcp_bridge_url.rstrip('/')}/api/chat"
    result = {
        "mcp_bridge_url": mcp_bridge_url,
        "health_url": health_url,
        "chat_url": chat_url,
    }
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:  # nosec B310
            body = resp.read().decode("utf-8", errors="replace")
        result["reachable"] = True
        result["health"] = body[:500]
        result["status"] = "success"
        try:
            health_json = json.loads(body)
            if isinstance(health_json, dict):
                for key in (
                    "llm_configured",
                    "llm_mode",
                    "llm_model",
                    "openai_base_url_set",
                    "openai_package_installed",
                    "llm_hint",
                ):
                    if key in health_json:
                        result[key] = health_json[key]
        except json.JSONDecodeError:
            pass
        if result.get("reachable") and "llm_configured" not in result:
            result["llm_configured"] = False
            result["llm_hint"] = (
                "Bridge health did not report LLM status — update MCP bridge to latest version."
            )
    except Exception as exc:  # noqa: BLE001
        result["reachable"] = False
        result["status"] = "error"
        result["error"] = str(exc)
        result["llm_configured"] = False
    return result


def _proxy_chat_to_bridge(body, mcp_bridge_url):
    bridge = mcp_bridge_url.rstrip("/")
    url = f"{bridge}/api/chat"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # MCP cold start + Ollama NL can exceed 45s; align with sidecar POST timeout (90s).
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310
            return _normalize_bridge_response(json.loads(resp.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return {
            "status": "error",
            "error": f"MCP bridge HTTP {exc.code} at {url}: {detail or exc.reason}",
        }
    except urllib.error.URLError as exc:
        health = _bridge_health_url(mcp_bridge_url)
        return {
            "status": "error",
            "error": (
                f"MCP bridge unreachable from SOAR at {url}: {exc}. "
                f"On the SOAR host run: curl {health}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error": f"MCP bridge error at {url}: {exc}",
        }


_KNOWN_ROUTES = frozenset({"chat", "widget", "list_lessons", "poll_playbook", "proxy_chat", "es_link", "splunk_link"})
_STATIC_WIDGETS = {
    "playbook_builder.js": "application/javascript",
    "playbook_builder.css": "text/css",
    "playbook_builder_logo.png": "image/png",
}


def _serve_static_widget(filename: str):
    """Serve React sidecar bundle from widgets/ via REST handler."""
    from django.http import HttpResponse

    path = os.path.join(os.path.dirname(__file__), "widgets", filename)
    try:
        with open(path, "rb") as fh:
            content = fh.read()
    except OSError:
        return HttpResponse(f"Missing widget asset: {filename}", status=404)
    return HttpResponse(content, content_type=_STATIC_WIDGETS[filename])


def _resolve_route(path_parts):
    """Map SOAR path_parts to handler route name.

    SOAR 8.x often passes ``[<asset>, <route>, ...]`` after the handler directory
    (e.g. ``mcpbridge/chat`` → ``['mcpbridge', 'chat']``). Older builds pass only
    ``[<route>]`` when the asset is already part of the handler URL prefix.
    """
    parts = path_parts or []
    if not parts:
        return "chat"
    for seg in reversed(parts):
        if seg in _STATIC_WIDGETS:
            return seg
    if parts[0] in _KNOWN_ROUTES:
        return parts[0]
    if len(parts) >= 2 and parts[1] in _KNOWN_ROUTES:
        return parts[1]
    # Asset-only URL (.../mcpbridge) — default to chat sidecar
    return "chat"


def _merge_asset_configuration(asset: dict) -> dict:
    """SOAR stores custom fields in a nested configuration blob on REST responses."""
    merged = dict(asset or {})
    cfg_blob = merged.get("configuration")
    if isinstance(cfg_blob, str):
        try:
            cfg_blob = json.loads(cfg_blob)
        except json.JSONDecodeError:
            cfg_blob = {}
    if isinstance(cfg_blob, dict):
        for key, val in cfg_blob.items():
            if key not in merged or not str(merged.get(key) or "").strip():
                merged[key] = val
    return merged


def _fetch_asset_config_by_name(request, asset_name: str) -> dict:
    if not asset_name:
        return {}
    from asset_resolver import assets_from_rest, _asset_field  # noqa: PLC0415
    from soar_rest import django_request_rest  # noqa: PLC0415

    ok, resp, _ = django_request_rest(request, "GET", "asset", params={"page_size": 0})
    if not ok:
        return {}
    for record in assets_from_rest(resp):
        if _asset_field(record, "name") == asset_name:
            return _merge_asset_configuration(record)
    return {}


def _config_from_request(request, path_parts=None):
    """Read asset config when REST handler runs in asset context."""
    try:
        asset = phantom.get_current_asset() or {}
    except Exception:  # noqa: BLE001
        asset = {}
    asset = _merge_asset_configuration(asset)
    if not str(asset.get("asset_defaults") or "").strip() and path_parts:
        parts = path_parts or []
        asset_name = parts[0] if parts and parts[0] not in _KNOWN_ROUTES else ""
        if asset_name:
            fetched = _fetch_asset_config_by_name(request, asset_name)
            if fetched:
                asset = {**fetched, **asset}
    return {
        "mcp_bridge_url": asset.get("mcp_bridge_url") or "http://localhost:8003/agent",
        "ai_instructions": asset.get("ai_instructions") or "SOAR Playbook Builder",
        "soar_rest_token": (asset.get("soar_rest_token") or "").strip(),
        "phenv_use_sudo": asset.get("phenv_use_sudo", "true"),
        "phenv_path": (asset.get("phenv_path") or "").strip(),
        "asset_defaults": (asset.get("asset_defaults") or "").strip(),
        "custom_templates_json": (asset.get("custom_templates_json") or "").strip(),
        "playbook_defaults_json": (asset.get("playbook_defaults_json") or "").strip(),
        "es_web_url": (asset.get("es_web_url") or "").strip(),
        "sample_cases_json": (asset.get("sample_cases_json") or "").strip(),
        "operating_mode": (asset.get("operating_mode") or "connected").strip(),
        "default_ui_mode": (asset.get("default_ui_mode") or "studio").strip(),
    }


def _asset_name_from_path_parts(path_parts) -> str:
    parts = path_parts or []
    for seg in parts:
        if seg not in _KNOWN_ROUTES and seg not in _STATIC_WIDGETS:
            return seg
    return ""


def _handler_base_from_parts(path_parts) -> str:
    """REST handler base URL (.../rest/handler/<directory>/<asset>) for current request."""
    asset = _asset_name_from_path_parts(path_parts)
    directory = _handler_directory_slug()
    base = phantom.get_base_url().rstrip("/")
    return f"{base}/rest/handler/{directory}/{asset}"


def _parse_es_link_query(request) -> dict[str, Any]:
    """Read ES link query params from GET."""
    out: dict[str, Any] = {}
    for key in ("event_id", "rule_name", "investigation_id", "mode", "tab", "sid", "src", "dest", "user"):
        raw = getattr(request, "GET", {}).get(key)
        if raw not in (None, ""):
            out[key] = str(raw)
    for key in ("container_id", "playbook_id"):
        raw = getattr(request, "GET", {}).get(key)
        if raw in (None, ""):
            continue
        try:
            out[key] = int(raw)
        except (TypeError, ValueError):
            out[key] = raw
    return out


def handle_request(request, path_parts=None):
    """SOAR REST handler entry point."""
    from django.http import HttpResponse, JsonResponse

    def _json_chat(payload):
        return JsonResponse(_finalize_chat_payload(payload if isinstance(payload, dict) else {}))

    parts = path_parts or []
    route = _resolve_route(parts)
    cfg = _config_from_request(request, path_parts)
    if cfg.get("soar_rest_token"):
        request._soar_rest_token = cfg["soar_rest_token"]  # noqa: SLF001
    request._pb_config = cfg  # noqa: SLF001 — phenv_use_sudo / phenv_path for python39_upgrade
    from custom_templates import parse_org_templates

    request._pb_org_registry = parse_org_templates(cfg.get("custom_templates_json"))  # noqa: SLF001

    if route in _STATIC_WIDGETS:
        return _serve_static_widget(route)

    if route == "chat":
        if request.method == "POST":
            try:
                body = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                body = {}
            action = (body.get("action") or "").strip().lower()
            if action == "import_draft":
                try:
                    payload = _safe_enrich_builder_payload(
                        request, _handle_import_draft(request, body), auto_import=False
                    )
                except Exception as exc:  # noqa: BLE001
                    import traceback

                    payload = _finalize_chat_payload(
                        {
                            "status": "error",
                            "error": f"Import failed: {exc}",
                            "traceback": traceback.format_exc()[-800:],
                        }
                    )
                return JsonResponse(payload)
            try:
                return _json_chat(_handle_chat_api(request, cfg, post_body=body))
            except Exception as exc:  # noqa: BLE001
                import traceback

                return _json_chat(
                    {
                        "status": "error",
                        "error": f"Builder error: {exc}",
                        "traceback": traceback.format_exc()[-800:],
                    }
                )

        if request.method == "GET" and (
            request.GET.get("message")
            or request.GET.get("poll")
            or request.GET.get("action")
        ):
            try:
                return _json_chat(_handle_chat_api(request, cfg))
            except Exception as exc:  # noqa: BLE001
                import traceback

                return _json_chat(
                    {
                        "status": "error",
                        "error": f"Builder error: {exc}",
                        "traceback": traceback.format_exc()[-800:],
                    }
                )

        html = _render_template(
            "agent_chat.html",
            MCP_BRIDGE_URL=cfg["mcp_bridge_url"],
            AI_INSTRUCTIONS=cfg["ai_instructions"],
            DEFAULT_UI_MODE=cfg.get("default_ui_mode") or "studio",
        )
        return HttpResponse(html, content_type="text/html")

    if route == "widget":
        html = _render_template(
            "playbook_builder_widget.html",
            MCP_URL=cfg["mcp_bridge_url"],
            AI_INSTRUCTIONS=cfg["ai_instructions"],
        )
        return HttpResponse(html, content_type="text/html")

    if route == "list_lessons":
        return JsonResponse(handle_list_lessons({}))

    if route == "poll_playbook" and request.method == "GET" and request.GET.get("playbook_id"):
        return JsonResponse(
            handle_poll_playbook({"playbook_id": request.GET.get("playbook_id")})
        )

    if route == "poll_playbook" and request.method == "POST":
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            body = {}
        return JsonResponse(handle_poll_playbook(body))

    if route == "proxy_chat" and request.method == "POST":
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            body = {}
        return JsonResponse(_proxy_chat_to_bridge(body, cfg["mcp_bridge_url"]))

    if route == "es_link" and request.method == "GET":
        from django.http import HttpResponseRedirect

        from es_link import build_sidecar_chat_url, es_link_status_message, resolve_es_link_params

        query = _parse_es_link_query(request)
        handler_base = _handler_base_from_parts(parts)
        param = resolve_es_link_params(
            event_id=query.get("event_id"),
            rule_name=query.get("rule_name"),
            investigation_id=query.get("investigation_id"),
            container_id=query.get("container_id"),
            playbook_id=query.get("playbook_id"),
            request=request,
        )
        if query.get("mode"):
            param["mode"] = query["mode"]
        if query.get("tab"):
            param["tab"] = query["tab"]
        target = build_sidecar_chat_url(handler_base, param)
        if request.GET.get("format") == "json":
            return JsonResponse(
                {
                    "status": "ok",
                    "sidecar_url": target,
                    "context": param,
                    "message": es_link_status_message(param),
                }
            )
        return HttpResponseRedirect(target)

    if route == "splunk_link" and request.method == "GET":
        from django.http import HttpResponseRedirect

        from splunk_link import build_sidecar_chat_url, resolve_splunk_link_params, splunk_link_status_message

        query = _parse_es_link_query(request)
        handler_base = _handler_base_from_parts(parts)
        raw_cid = query.get("container_id")
        cid = None
        if raw_cid is not None:
            try:
                cid = int(raw_cid)
            except (TypeError, ValueError):
                cid = raw_cid
        param = resolve_splunk_link_params(
            sid=query.get("sid"),
            rule_name=query.get("rule_name"),
            src=query.get("src"),
            dest=query.get("dest"),
            user=query.get("user"),
            container_id=cid,
            mode=query.get("mode") or "coach",
            tab=query.get("tab") or "respond",
        )
        target = build_sidecar_chat_url(handler_base, param)
        if request.GET.get("format") == "json":
            return JsonResponse(
                {
                    "status": "ok",
                    "sidecar_url": target,
                    "context": param,
                    "message": splunk_link_status_message(param),
                }
            )
        return HttpResponseRedirect(target)

    return JsonResponse({"status": "error", "error": f"Unknown route: {route}"}, status=404)
