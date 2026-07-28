"""Reliable SOAR playbook catalog fetch (pagination differs on 6.x vs 8.x)."""

from __future__ import annotations

from typing import Any, Callable

RequestFn = Callable[..., tuple[bool, Any, list[str]]]


def playbooks_from_rest(resp: Any) -> list[dict[str, Any]]:
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


def rest_total_count(resp: Any) -> int | None:
    if not isinstance(resp, dict):
        return len(resp) if isinstance(resp, list) else None
    for key in ("count", "total", "total_count", "_total", "totalCount"):
        val = resp.get(key)
        if isinstance(val, int):
            return val
    return None


def _dedupe_playbooks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            pid = int(row.get("id"))
        except (TypeError, ValueError):
            out.append(row)
            continue
        if pid in seen:
            continue
        seen.add(pid)
        out.append(row)
    return out


def fetch_playbooks_via_phantom_rest(
    phantom_rest: Callable[..., tuple[bool, Any]],
    *,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch catalog using phantom.rest-style (GET only) helper."""

    def _get(params: dict[str, Any]) -> tuple[bool, Any]:
        ok, resp = phantom_rest("GET", "playbook", None, params=params)
        return ok, resp

    rows, strategy = _fetch_with_strategies(_get, attempts_log)
    if attempts_log is not None:
        attempts_log.append(f"playbook catalog via phantom.rest: {strategy} rows={len(rows)}")
    return rows


def fetch_playbooks_django(
    django_rest: RequestFn,
    request: Any,
    *,
    attempts_log: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch full playbook catalog from a REST handler context."""

    def _get(params: dict[str, Any]) -> tuple[bool, Any]:
        ok, resp, _ = django_rest("GET", "playbook", None, params=params, request=request)
        return ok, resp

    rows, strategy = _fetch_with_strategies(_get, attempts_log)
    if attempts_log is not None:
        attempts_log.append(f"playbook catalog via loopback: {strategy} rows={len(rows)}")
    return rows


def fetch_playbooks_httpx(client: Any, *, attempts_log: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch full playbook catalog via httpx Client (Mac-side scripts)."""

    def _get(params: dict[str, Any]) -> tuple[bool, Any]:
        r = client.get("/rest/playbook", params=params)
        if r.status_code >= 400:
            return False, r.text[:300]
        return True, r.json()

    rows, strategy = _fetch_with_strategies(_get, attempts_log)
    if attempts_log is not None:
        attempts_log.append(f"playbook catalog via httpx: {strategy} rows={len(rows)}")
    return rows


def _fetch_with_strategies(
    get_fn: Callable[[dict[str, Any]], tuple[bool, Any]],
    attempts_log: list[str] | None,
) -> tuple[list[dict[str, Any]], str]:
    strategies: list[tuple[str, dict[str, Any] | None, bool]] = [
        ("page_size=0", {"page_size": 0}, True),
        ("_page_size=0", {"_page_size": 0}, True),
        ("page=0 page_size=500", {"page": 0, "page_size": 500}, False),
        ("_page=0 _page_size=500", {"_page": 0, "_page_size": 500}, False),
        ("_page=1 _page_size=500", {"_page": 1, "_page_size": 500}, False),
    ]

    best: list[dict[str, Any]] = []
    best_name = "none"

    for name, params, single_shot in strategies:
        if params is None:
            continue
        if single_shot:
            ok, resp = get_fn(params)
            if attempts_log is not None:
                attempts_log.append(f"GET playbook {params} -> ok={ok} rows={len(playbooks_from_rest(resp)) if ok else 0}")
            if not ok:
                continue
            rows = playbooks_from_rest(resp)
            if len(rows) > len(best):
                best, best_name = rows, name
            if rows and rest_total_count(resp) == len(rows):
                return _dedupe_playbooks(rows), name
            continue

        merged: list[dict[str, Any]] = []
        for page in range(0, 100):
            page_params = dict(params)
            if "_page" in page_params:
                page_params["_page"] = page + 1 if page_params.get("_page") == 1 else page
            else:
                page_params["page"] = page
            ok, resp = get_fn(page_params)
            if not ok:
                break
            batch = playbooks_from_rest(resp)
            if not batch:
                break
            merged.extend(batch)
            total = rest_total_count(resp)
            if total is not None and len(merged) >= total:
                break
            size_key = "_page_size" if "_page_size" in page_params else "page_size"
            page_size = int(page_params.get(size_key) or 500)
            if len(batch) < page_size:
                break
        merged = _dedupe_playbooks(merged)
        if attempts_log is not None:
            attempts_log.append(f"GET playbook paginated {name} -> rows={len(merged)}")
        if len(merged) > len(best):
            best, best_name = merged, name

    return _dedupe_playbooks(best), best_name


def playbook_repo(record: dict[str, Any]) -> str:
    for key in ("repo", "repository", "scm", "scm_name"):
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip().lower()
    name = str(record.get("name") or "")
    if "/" in name:
        return name.split("/")[0].lower()
    path = str(record.get("scm_path") or record.get("path") or "")
    if "/" in path:
        return path.split("/")[0].lower()
    return "local"
