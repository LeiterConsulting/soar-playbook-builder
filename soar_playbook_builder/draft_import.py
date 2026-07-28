"""Package NL-built playbook source and import into SOAR via REST."""

from __future__ import annotations

import base64
import gzip
import io
import json
import re
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable

from soar_rest import django_request_rest, phantom_rest_call

BUILDER_LABEL = "playbook_builder"
DEFAULT_PLAYBOOK_PYTHON_VERSION = "3.13"
REST_TIMEOUT_SEC = 30
RESOLVE_POLL_SEC = 2.0
RESOLVE_MAX_POLLS = 8


def python_version_value(record: dict[str, Any] | None) -> str:
    if not record:
        return ""
    for key in ("python_version", "pythonVersion", "py_version"):
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def is_python_39(record: dict[str, Any] | None) -> bool:
    """True for any Python 3.x runtime (3, 3.6, 3.9, 3.13 on different SOAR releases)."""
    ver = python_version_value(record).lower()
    if not ver or ver.startswith("2"):
        return False
    return ver.startswith("3")


def is_legacy_python27(record: dict[str, Any] | None) -> bool:
    ver = python_version_value(record).lower()
    if not ver:
        return True
    return ver.startswith("2")


def slug_from_label(label: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", (label or "").lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:48]
    return slug or "nl_draft_playbook"


def playbook_search_term(
    slug: str,
    display_name: str = "",
    record_name: str = "",
) -> str:
    """Search string that matches SOAR Playbooks UI (classic names are slug-based)."""
    if record_name:
        scm = _scm_slug_from_record_name(record_name)
        if scm:
            return scm
    if slug:
        return slug
    return slug_from_label(display_name or record_name)


def _import_followup_notes(record: dict[str, Any] | None, *, modern: bool = False) -> str:
    """Post-import guidance for Python version and SOAR Data Preview expectations."""
    lines: list[str] = []
    if is_python_39(record):
        lines.append(
            f"**Python version:** **{python_version_value(record) or DEFAULT_PLAYBOOK_PYTHON_VERSION}** "
            + ("(modern COA import)." if modern else "(metadata + auto-upgrade).")
        )
    elif is_legacy_python27(record):
        py_ver = python_version_value(record)
        lines.append(
            f"**Python version:** Still **{py_ver or '2.7'}**. "
            "Open the playbook → **Settings → Update Python Version → 3.13 → Save**."
        )
    elif python_version_value(record):
        lines.append(
            f"**Python version:** SOAR reports `{python_version_value(record)}` — set **{DEFAULT_PLAYBOOK_PYTHON_VERSION}** under "
            "**Playbook Settings** or re-import with Playbook Builder **≥ 2.8.0**."
        )
    else:
        lines.append(
            f"**Python version:** Import metadata requests **{DEFAULT_PLAYBOOK_PYTHON_VERSION}**."
        )
    if modern:
        lines.append(
            "**Visual editor:** Imported as a **modern** playbook with COA blocks. "
            "Open **?editor=visual** in SOAR to edit blocks; run once to populate Block results."
        )
    else:
        lines.append(
            "**Block results in SOAR:** Classic `.py` imports use the **Python editor**; "
            "re-import with Playbook Builder **≥ 2.8.0** for modern/visual playbooks."
        )
    lines.append(
        "**Pylint `no-member` on `phantom.*`:** Expected — SOAR injects "
        "`phantom.app` at runtime. Imports include `# pylint: disable=no-member`."
    )
    return "\n\n".join(lines)


def _normalize_playbook_source_for_import(source: str) -> str:
    """Prep source for SOAR 3.9 validation (phantom.app pylint false positives)."""
    text = (source or "").strip()
    if not text:
        return text
    if "pylint: disable=no-member" in text:
        return text
    marker = "import phantom.app as phantom"
    if marker in text:
        return text.replace(marker, f"# pylint: disable=no-member\n{marker}", 1)
    return f"# pylint: disable=no-member\n{text}"


def build_playbook_metadata(
    name: str,
    pattern: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Build sidecar JSON metadata; ``name`` must match tarball folder/slug."""
    display_name = (name or "NL Draft Playbook").strip()
    slug = slug_from_label(display_name)
    tag_labels = list(labels or [])
    for tag in (BUILDER_LABEL, slug.replace("-", "_")):
        if tag not in tag_labels:
            tag_labels.append(tag)
    if pattern and pattern.replace("-", "_") not in tag_labels:
        tag_labels.append(pattern.replace("-", "_"))
    return {
        "name": display_name,
        "description": f"Created by SOAR Playbook Builder — {display_name}",
        "labels": tag_labels[:8],
        "active": True,
        "draft": False,
        "disabled": False,
        "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION,
    }


def package_source_with_metadata_b64(source: str, slug: str, metadata: dict[str, Any]) -> str:
    """Root-level ``slug.py`` + ``slug.json`` — avoids ``slug/slug`` SCM path on SOAR 8.x."""
    tar_buf = io.BytesIO()
    py_bytes = source.encode("utf-8")
    json_bytes = json.dumps(metadata, indent=2).encode("utf-8")
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        for arcname, data in (
            (f"{slug}.py", py_bytes),
            (f"{slug}.json", json_bytes),
        ):
            info = tarfile.TarInfo(name=arcname)
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))
    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb") as gz:
        gz.write(tar_buf.getvalue())
    return base64.b64encode(gz_buf.getvalue()).decode("ascii")


def package_source_flat_py_b64(source: str, slug: str) -> str:
    """Flat single-file tarball — SOAR 6.x classic import compatibility."""
    tar_buf = io.BytesIO()
    py_bytes = source.encode("utf-8")
    arcname = f"{slug}.py"
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        info = tarfile.TarInfo(name=arcname)
        info.size = len(py_bytes)
        tar.addfile(info, fileobj=io.BytesIO(py_bytes))
    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb") as gz:
        gz.write(tar_buf.getvalue())
    return base64.b64encode(gz_buf.getvalue()).decode("ascii")


def _import_api_succeeded(resp: Any) -> bool:
    if resp is None:
        return False
    if isinstance(resp, bool):
        return resp
    if isinstance(resp, str):
        return bool(resp.strip())
    if isinstance(resp, dict):
        if resp.get("failed") is True:
            return False
        if resp.get("success") is False:
            return False
        if resp.get("error"):
            return False
        message = str(resp.get("message") or "")
        if message and any(word in message.lower() for word in ("fail", "error", "invalid")):
            return False
    return True


def _normalize_record_name(name: str) -> str:
    """Prefer human title; SOAR may store SCM paths like ``hello_world/hello_world``."""
    text = (name or "").strip()
    if "/" not in text:
        return text
    parts = [p for p in text.split("/") if p]
    if not parts:
        return text
    if len(parts) >= 2 and parts[0] == parts[-1]:
        return parts[0].replace("_", " ").title()
    return parts[-1].replace("_", " ").title()


def _scm_slug_from_record_name(name: str) -> str:
    """Repo slug segment from SOAR name/path."""
    text = (name or "").strip()
    if "/" in text:
        parts = [p for p in text.split("/") if p]
        return parts[0] if parts else slug_from_label(text)
    return slug_from_label(text)


def _record_matches_import(
    record: dict[str, Any] | None,
    display_name: str,
    slug: str,
) -> bool:
    if not record:
        return False
    raw = str(record.get("name") or "").strip()
    if not raw:
        return False
    slug_l = slug.lower()
    display_l = display_name.strip().lower()
    tokens = {raw.lower(), _scm_slug_from_record_name(raw).lower(), slug_from_label(raw)}
    if "/" in raw:
        tokens.update(p.lower() for p in raw.split("/") if p)
    if raw.lower() == display_l:
        return True
    if slug_l in tokens:
        return True
    if slug_l in raw.lower().replace("-", "_").replace(" ", "_"):
        return True
    norm = _normalize_record_name(raw).lower()
    return norm == display_l or slug_from_label(norm) == slug_l


def _json_safe(value: Any) -> Any:
    """Ensure REST handler responses are JsonResponse-safe."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _json_safe_playbook_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    keep = (
        "id",
        "name",
        "description",
        "labels",
        "tags",
        "scm_path",
        "path",
        "python_version",
        "playbook_type",
        "disabled",
        "active",
    )
    return {k: _json_safe(record[k]) for k in keep if k in record}


def _catalog_rows_from_snapshot(
    rows: list[dict[str, Any]],
    display_name: str,
    slug: str,
) -> dict[str, Any] | None:
    """Find imported playbook in a cached catalog snapshot (no extra REST)."""
    slug_l = slug.lower()
    display_l = display_name.strip().lower()
    for row in rows:
        raw = str(row.get("name") or "")
        if _record_matches_import(row, display_name, slug):
            return row
        scm_path = str(row.get("scm_path") or row.get("path") or "").lower()
        if slug_l in scm_path or display_l in raw.lower():
            return row
    return None


def _fetch_catalog_once(
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Paginated playbook list — SOAR 6.x defaults to 10 rows without page_size=0."""
    from soar_playbook_list import fetch_playbooks_django, fetch_playbooks_via_phantom_rest

    if request is not None:
        return fetch_playbooks_django(_phantom_rest, request, attempts_log=attempts_log)

    def _get(params: dict[str, Any] | None = None) -> tuple[bool, Any]:
        ok, result = phantom_rest_call("GET", "playbook", None, params=params, request=None)
        return ok, result

    return fetch_playbooks_via_phantom_rest(_get, attempts_log=attempts_log)


def _playbook_in_catalog_rows(
    rows: list[dict[str, Any]],
    playbook_id: int,
    display_name: str,
    slug: str,
) -> dict[str, Any] | None:
    for row in rows:
        try:
            row_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        if row_id != playbook_id:
            continue
        if _record_matches_import(row, display_name, slug):
            return row
    return None


def _run_with_timeout(
    fn: Callable[[], tuple[bool, Any] | tuple[bool, Any, list[str]]],
    timeout: int = REST_TIMEOUT_SEC,
) -> tuple[bool, Any, list[str]]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            result = fut.result(timeout=timeout)
            if len(result) == 3:
                return result  # type: ignore[return-value]
            ok, payload = result  # type: ignore[misc]
            return ok, payload, []
        except FuturesTimeoutError:
            return False, f"SOAR REST call timed out after {timeout}s", []
        except Exception as exc:  # noqa: BLE001
            return False, str(exc), []


def _phantom_rest(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    params: dict[str, Any] | None = None,
    request: Any | None = None,
) -> tuple[bool, Any, list[str]]:
    if request is not None:
        return django_request_rest(request, method, path, body, params=params)
    ok, result = phantom_rest_call(method, path, body, params=params, request=None)
    return ok, result, []


def _local_scm_id(request: Any | None = None) -> int | None:
    ok, resp, _ = _phantom_rest("GET", "scm", request=request)
    if not ok:
        return 2
    rows = resp if isinstance(resp, list) else resp.get("data") if isinstance(resp, dict) else []
    if not isinstance(rows, list):
        return 2
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").lower()
        if name in {"local", "default"} or row.get("id") == 2:
            try:
                return int(row["id"])
            except (TypeError, ValueError, KeyError):
                continue
    for row in rows:
        if isinstance(row, dict) and row.get("id") is not None:
            try:
                return int(row["id"])
            except (TypeError, ValueError):
                continue
    return 2


def import_playbook_b64(
    playbook_b64: str,
    *,
    scm_id: int | None = None,
    force: bool = True,
    request: Any | None = None,
) -> tuple[bool, Any, list[str]]:
    """Try import variants; return (ok, response, attempts_log)."""
    scm_id = scm_id or _local_scm_id(request) or 2
    attempts_log: list[str] = []
    # Match MCP SOAR: scm_id + force only first (SOAR 6.5/8.x).
    bodies = [
        {"playbook": playbook_b64, "scm_id": scm_id, "force": force},
        {"playbook": playbook_b64, "scm": "local", "scm_id": scm_id, "force": force},
        {"playbook": playbook_b64, "scm": "local", "force": force},
    ]
    last_resp: Any = None
    for body in bodies:
        def _do_import(b=body) -> tuple[bool, Any, list[str]]:
            return _phantom_rest("POST", "import_playbook", b, request=request)

        ok, resp, loopback_log = _run_with_timeout(_do_import)
        attempts_log.extend(loopback_log)
        attempts_log.append(
            f"import_playbook {json.dumps({k: v for k, v in body.items() if k != 'playbook'})} -> {ok}"
        )
        if ok:
            attempts_log.append(f"import_playbook response: {_summarize_rest_payload(resp)}")
        if ok and not _import_api_succeeded(resp):
            attempts_log.append(f"import_playbook rejected payload: {resp}")
            ok = False
        if ok:
            # Do not scm pull after import — pull can overwrite a fresh local import on
            # classic SOAR (MCP soar_import_playbook does not pull either).
            return True, resp, attempts_log
        last_resp = resp
    return False, last_resp, attempts_log


def _summarize_rest_payload(resp: Any, limit: int = 240) -> str:
    try:
        text = json.dumps(resp, default=str)
    except TypeError:
        text = str(resp)
    return text[:limit]


def _playbooks_from_rest(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, list):
        return [p for p in resp if isinstance(p, dict)]
    if isinstance(resp, dict):
        for key in ("data", "playbooks", "items", "results"):
            data = resp.get(key)
            if isinstance(data, list):
                return [p for p in data if isinstance(p, dict)]
            if isinstance(data, dict) and data.get("id") is not None:
                return [data]
        if resp.get("id") is not None and resp.get("name"):
            return [resp]
    return []


def _list_playbooks(
    request: Any | None = None,
    *,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    return _fetch_catalog_once(request, attempts_log=attempts_log)


def find_playbook_by_name(name: str, request: Any | None = None) -> dict[str, Any] | None:
    norm = _normalize_record_name(name).lower()
    matches = [
        p
        for p in _list_playbooks(request)
        if _normalize_record_name(str(p.get("name") or "")).lower() == norm
        or str(p.get("name") or "").lower() == name.lower()
    ]
    if not matches:
        return None
    matches.sort(key=lambda p: p.get("id") or 0, reverse=True)
    return matches[0]


def find_playbook_by_slug(
    slug: str,
    request: Any | None = None,
    *,
    allow_builder_fallback: bool = False,
) -> dict[str, Any] | None:
    slug_l = slug.lower()
    matches: list[dict[str, Any]] = []
    for p in _list_playbooks(request):
        name = str(p.get("name") or "").lower()
        scm_path = str(p.get("scm_path") or p.get("path") or "").lower()
        if slug_l in scm_path or slug_l == slug_from_label(name):
            matches.append(p)
    if matches:
        matches.sort(key=lambda p: p.get("id") or 0, reverse=True)
        return matches[0]
    if not allow_builder_fallback:
        return None
    builder = [
        p
        for p in _list_playbooks(request)
        if BUILDER_LABEL in (p.get("labels") or []) or BUILDER_LABEL in (p.get("tags") or [])
    ]
    builder.sort(key=lambda p: p.get("id") or 0, reverse=True)
    return builder[0] if builder else None


def _playbook_record_from_rest(resp: Any) -> dict[str, Any] | None:
    if isinstance(resp, list) and resp:
        row = resp[0]
        return row if isinstance(row, dict) else None
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        if resp.get("id") is not None:
            return resp
    return None


def _get_playbook_by_id(request: Any | None, playbook_id: int) -> dict[str, Any] | None:
    ok, resp, _ = _phantom_rest("GET", f"playbook/{playbook_id}", request=request)
    if not ok:
        return None
    return _playbook_record_from_rest(resp)


def _delete_playbook(
    playbook_id: int,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> bool:
    """Best-effort delete. SOAR REST does not support DELETE on /rest/playbook (returns 405)."""
    ok, resp, log = _phantom_rest("DELETE", f"playbook/{playbook_id}", request=request)
    if attempts_log is not None:
        attempts_log.extend(log)
        attempts_log.append(
            f"DELETE playbook/{playbook_id} -> {ok} {_summarize_rest_payload(resp)}"
        )
    if ok:
        return True
    detail = _summarize_rest_payload(resp)
    if "405" in detail or "not allowed" in detail.lower():
        if attempts_log is not None:
            attempts_log.append(
                "SOAR REST cannot DELETE playbooks — remove in Playbooks UI, then re-import"
            )
    return False


def _pin_playbook_python_version(
    playbook_id: int,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
    version: str = DEFAULT_PLAYBOOK_PYTHON_VERSION,
) -> dict[str, Any] | None:
    """Best-effort REST pin after import (metadata .json is primary)."""
    candidates: list[Any] = [version, "3"]
    if version != "3":
        try:
            candidates.append(float(version))
        except ValueError:
            pass
    for candidate in candidates:
        body = {"python_version": candidate}
        ok, resp, log = _phantom_rest(
            "POST",
            f"playbook/{playbook_id}",
            body,
            request=request,
        )
        if attempts_log is not None:
            attempts_log.extend(log)
            attempts_log.append(
                f"POST playbook/{playbook_id} python_version={candidate!r} -> {ok} "
                f"{_summarize_rest_payload(resp)}"
            )
        record = _get_playbook_by_id(request, playbook_id)
        if record and is_python_39(record):
            return record
    return _get_playbook_by_id(request, playbook_id)


def _verify_imported_playbook(
    request: Any | None,
    playbook_id: int,
    display_name: str,
    slug: str,
    *,
    catalog_rows: list[dict[str, Any]] | None = None,
    attempts_log: list[str] | None = None,
    trust_import_api: bool = False,
) -> dict[str, Any] | None:
    """Verify playbook id — GET-by-id first when import API returned the id."""
    record = _get_playbook_by_id(request, playbook_id)
    if record and _record_matches_import(record, display_name, slug):
        return record
    if trust_import_api and record:
        if attempts_log is not None:
            attempts_log.append(
                f"accept import API id {playbook_id} (GET playbook name={record.get('name')!r})",
            )
        return record
    rows = (
        catalog_rows
        if catalog_rows is not None
        else _fetch_catalog_once(request, attempts_log=attempts_log)
    )
    return _playbook_in_catalog_rows(rows, playbook_id, display_name, slug)


def _wait_for_imported_playbook(
    name: str,
    slug: str,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Poll SOAR catalog lightly until the imported playbook appears."""
    for attempt in range(RESOLVE_MAX_POLLS):
        rows = _fetch_catalog_once(
            request,
            attempts_log=attempts_log if attempt == 0 else None,
        )
        found = _catalog_rows_from_snapshot(rows, name, slug)
        if found and found.get("id") is not None:
            try:
                pid = int(found["id"])
            except (TypeError, ValueError):
                pid = None
            if pid is not None:
                verified = _verify_imported_playbook(
                    request,
                    pid,
                    name,
                    slug,
                    catalog_rows=rows,
                    attempts_log=attempts_log,
                )
                if verified:
                    return pid, verified
        if attempt + 1 < RESOLVE_MAX_POLLS:
            time.sleep(RESOLVE_POLL_SEC)
    return None, None


def _candidate_ids_from_import_response(resp: Any) -> list[int]:
    ids: list[int] = []
    buckets: list[Any] = []
    if isinstance(resp, dict):
        buckets.append(resp)
        data = resp.get("data")
        if isinstance(data, dict):
            buckets.append(data)
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        for key in ("id", "playbook_id"):
            raw = bucket.get(key)
            if raw is None:
                continue
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                continue
            if pid not in ids:
                ids.append(pid)
    return ids


def _playbook_id_from_import_response(
    resp: Any,
    name: str,
    slug: str,
    request: Any | None = None,
    *,
    attempts_log: list[str] | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    import_ok = _import_api_succeeded(resp)
    for candidate in _candidate_ids_from_import_response(resp):
        verified = _verify_imported_playbook(
            request,
            candidate,
            name,
            slug,
            attempts_log=attempts_log,
            trust_import_api=import_ok,
        )
        if verified:
            return candidate, verified

    pid, verified = _wait_for_imported_playbook(
        name, slug, request, attempts_log=attempts_log,
    )
    if pid and verified:
        return pid, verified

    return None, None


def import_nl_draft(
    source: str,
    name: str,
    pattern: str | None = None,
    *,
    request: Any | None = None,
    asset_map: dict[str, str] | None = None,
    asset_defaults: dict[str, str] | None = None,
    skip_asset_check: bool = False,
) -> dict[str, Any]:
    """Import cached NL draft; returns scaffold-shaped payload with playbook_id."""
    if not (source or "").strip():
        return {"status": "error", "error": "No playbook source to import."}

    from asset_resolver import (
        apply_asset_map_to_source,
        build_asset_preflight,
        preflight_message,
    )

    preflight_attempts: list[str] = []
    preflight = build_asset_preflight(
        source,
        request,
        overrides=asset_map,
        defaults=asset_defaults,
        attempts_log=preflight_attempts,
    )

    if not preflight.get("ready") and not skip_asset_check:
        base = ""
        if request is not None and hasattr(request, "build_absolute_uri"):
            try:
                base = request.build_absolute_uri("/").rstrip("/")
            except Exception:  # noqa: BLE001
                base = ""
        return {
            "status": "needs_assets",
            "asset_preflight": preflight,
            "import_attempts": preflight_attempts,
            "content": preflight_message(preflight, base_url=base),
            "source": source,
            "pattern": pattern,
            "pattern_label": name,
            "draft_ready": True,
        }

    resolved_map = preflight.get("asset_map") or {}
    source = _normalize_playbook_source_for_import(source)
    if resolved_map:
        source = apply_asset_map_to_source(source, resolved_map)

    display_name = (name or "NL Draft Playbook").strip()
    slug = slug_from_label(display_name)
    from builder_helpers import preview_blocks_from_source
    from coa_builder import build_modern_playbook_json

    preview = preview_blocks_from_source(source)
    metadata = build_modern_playbook_json(
        source,
        display_name,
        pattern=pattern,
        preview_blocks=preview,
        asset_map=resolved_map,
    )
    modern_import = True
    steps: list[dict[str, Any]] = [
        {
            "id": "assets",
            "label": "Asset preflight",
            "status": "done",
            "detail": (
                ", ".join(f"{k}→{v}" for k, v in resolved_map.items())
                if resolved_map
                else "No external assets required"
            ),
        },
        {
            "id": "package",
            "label": "Packaged playbook files",
            "status": "done",
            "detail": f"{slug}.py + {slug}.json (modern COA, Python {DEFAULT_PLAYBOOK_PYTHON_VERSION})",
        },
    ]
    upload_step: dict[str, Any] = {
        "id": "upload",
        "label": "Uploading to SOAR (import_playbook)",
        "status": "running",
    }
    steps.append(upload_step)
    meta_b64 = package_source_with_metadata_b64(source, slug, metadata)

    attempts: list[str] = [
        f"import order: modern COA .py+.json (Python {DEFAULT_PLAYBOOK_PYTHON_VERSION}, visual editor)",
    ]
    existing = find_playbook_by_slug(slug, request)
    if existing and is_legacy_python27(existing):
        old_id = int(existing["id"])
        delete_step: dict[str, Any] = {
            "id": "delete_legacy",
            "label": "Removing legacy Python 2.7 copy",
            "status": "running",
            "detail": f"id {old_id}",
        }
        steps.insert(1, delete_step)
        deleted = _delete_playbook(old_id, request, attempts_log=attempts)
        if deleted:
            delete_step["status"] = "done"
            time.sleep(1.0)
        else:
            delete_step["status"] = "warning"
            delete_step["detail"] = (
                f"REST DELETE unsupported (id {old_id}) — delete `{slug}` in Playbooks UI, "
                f"then Import again. Attempting force import anyway."
            )
            attempts.append(
                f"legacy 2.7 playbook id {old_id} remains; SOAR REST DELETE returns 405"
            )

    ok_meta, resp_meta, attempts_meta = import_playbook_b64(meta_b64, request=request)
    attempts.extend(attempts_meta)
    resp: Any = resp_meta
    if not ok_meta:
        upload_step["status"] = "error"
        upload_step["detail"] = str(resp_meta)[:240]
        return {
            "status": "error",
            "error": (
                f"import_playbook with {DEFAULT_PLAYBOOK_PYTHON_VERSION} metadata failed: {resp_meta}. "
                "Flat .py-only import is disabled because classic SOAR creates Python 2.7 playbooks without metadata."
            ),
            "import_attempts": attempts,
            "import_steps": steps,
        }

    playbook_id, found = _playbook_id_from_import_response(
        resp, display_name, slug, request, attempts_log=attempts,
    )

    upload_step["status"] = "done"
    steps.append(
        {
            "id": "scm",
            "label": "SCM sync",
            "status": "skipped",
            "detail": "Skipped post-import pull (avoids overwriting local import on SOAR 6.x)",
        }
    )
    steps.append(
        {
            "id": "resolve",
            "label": "Resolving playbook ID",
            "status": "done" if playbook_id else "running",
            "detail": f"id {playbook_id}" if playbook_id else "",
        }
    )

    if not playbook_id:
        steps[-1]["status"] = "error"
        steps[-1]["detail"] = f"Search Playbooks for {slug}"
        list_count = len(_list_playbooks(request, attempts_log=attempts))
        return {
            "status": "error",
            "error": (
                "Import API returned success but the playbook was not found in SOAR. "
                f"Search Playbooks for **`{slug}`** (Classic mode tab on SOAR 6.x). "
                f"Catalog list returned {list_count} playbook(s). "
                "Check import_attempts in the chat log for REST diagnostics."
            ),
            "import_response": _json_safe(resp),
            "import_attempts": attempts,
            "import_steps": steps,
        }

    steps[-1]["status"] = "done"
    steps[-1]["detail"] = f"id {playbook_id}"

    py_step: dict[str, Any] = {
        "id": "python_version",
        "label": f"Python {DEFAULT_PLAYBOOK_PYTHON_VERSION}",
        "status": "running",
    }
    steps.append(py_step)

    final_id = int(playbook_id)
    final_record = found
    pinned = _pin_playbook_python_version(final_id, request, attempts_log=attempts)
    if pinned:
        final_record = pinned
    py_ver = python_version_value(final_record)
    if final_record and is_python_39(final_record):
        py_step["status"] = "done"
        py_step["detail"] = py_ver or DEFAULT_PLAYBOOK_PYTHON_VERSION
    elif final_record and is_legacy_python27(final_record):
        py_step["status"] = "warning"
        py_step["detail"] = (
            "Still 2.7 after modern import — use Playbooks UI: "
            "Settings → Update Python Version → 3.13"
        )
        attempts.append("modern import landed on 2.7; phenv skipped (not on SOAR 6.x)")
    else:
        py_step["status"] = "done"
        py_step["detail"] = DEFAULT_PLAYBOOK_PYTHON_VERSION

    playbook_id = final_id
    found = final_record

    resolved_name = (found or {}).get("name") or display_name
    search_term = playbook_search_term(slug, display_name, resolved_name)
    safe_record = _json_safe_playbook_record(found)
    vpe_hint = f"{search_term}?editor=visual" if modern_import else search_term
    return {
        "status": "success",
        "playbook_id": playbook_id,
        "playbook_name": resolved_name,
        "playbook_display_name": display_name,
        "playbook_slug": slug,
        "playbook_search": search_term,
        "playbook_record": safe_record,
        "pattern": pattern,
        "pattern_label": display_name,
        "source": source,
        "imported": True,
        "import_mode": "modern" if modern_import else "classic",
        "import_attempts": attempts,
        "import_steps": steps,
        "content": (
            f"✓ Imported **{display_name}** into SOAR as **`{search_term}`** (id **{playbook_id}**).\n\n"
            f"Open the **Visual Editor** (`{vpe_hint}`) to see playbook blocks."
            + (
                f"\n\n{_import_followup_notes(safe_record, modern=modern_import)}"
                if safe_record
                else f"\n\n{_import_followup_notes(None, modern=modern_import)}"
            )
        ),
    }
