"""Automatic Python 3 upgrade for classic SOAR 6.x playbooks via phenv."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from draft_import import (
    DEFAULT_PLAYBOOK_PYTHON_VERSION,
    _delete_playbook,
    _get_playbook_by_id,
    _list_playbooks,
    _pin_playbook_python_version,
    _scm_slug_from_record_name,
    find_playbook_by_slug,
    is_legacy_python27,
    is_python_39,
    playbook_search_term,
    python_version_value,
    slug_from_label,
)

PHENV_SUFFIXES = ("_py3", "_py39", "_py313")
PHENV_POLL_SEC = 1.5
PHENV_MAX_POLLS = 15
APP_ROOT = Path(__file__).resolve().parent
PHENV_WRAPPER = APP_ROOT / "bin" / "phenv_upgrade.sh"
PLAYBOOKS_TO_PY3_NAMES = ("playbooks_to_py3", "playbooks_to_py3.py")


def _phenv_config(request: Any | None) -> dict[str, Any]:
    cfg = getattr(request, "_pb_config", None) or {}
    use_sudo_raw = str(cfg.get("phenv_use_sudo", "true")).lower()
    return {
        "use_sudo": use_sudo_raw in ("1", "true", "yes"),
        "phenv_path": str(cfg.get("phenv_path") or "").strip(),
    }


def _phantom_home() -> str:
    for key in ("PHANTOM_HOME", "SOAR_HOME"):
        val = os.environ.get(key, "").strip()
        if val:
            return val.rstrip("/")
    return "/opt/phantom"


def find_phenv(request: Any | None = None) -> str | None:
    cfg = _phenv_config(request)
    if cfg["phenv_path"] and os.path.isfile(cfg["phenv_path"]):
        return cfg["phenv_path"]
    for candidate in (
        f"{_phantom_home()}/bin/phenv",
        "/opt/phantom/bin/phenv",
        "/usr/local/phantom/bin/phenv",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def find_playbooks_to_py3(request: Any | None = None) -> str | None:
    """Locate playbooks_to_py3 script (may be absent on SOAR 8.x)."""
    home = _phantom_home()
    candidates = [
        f"{home}/bin/{name}" for name in PLAYBOOKS_TO_PY3_NAMES
    ] + [
        f"{home}/usr/bin/{name}" for name in PLAYBOOKS_TO_PY3_NAMES
    ] + [
        f"{home}/share/{name}" for name in PLAYBOOKS_TO_PY3_NAMES
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    for sub in ("bin", "share", "usr/bin", "usr/local/bin"):
        base = os.path.join(home, sub)
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.listdir(base):
                if entry.startswith("playbooks_to_py3"):
                    full = os.path.join(base, entry)
                    if os.path.isfile(full):
                        return full
        except OSError:
            continue
    return None


def phenv_tool_status(request: Any | None = None) -> tuple[bool, str]:
    """Check whether 2.7→3 conversion tooling exists on this SOAR host."""
    tool = find_playbooks_to_py3(request)
    if tool:
        return True, tool
    phenv = find_phenv(request)
    if not phenv:
        return False, "phenv not found at /opt/phantom/bin/phenv"
    cfg = _phenv_config(request)
    prefix = _phenv_command_prefix(cfg["use_sudo"])
    pre = " ".join(shlex.quote(p) for p in prefix) if prefix else ""
    phenv_q = shlex.quote(phenv)
    cmd = f"{pre} {phenv_q} playbooks_to_py3 -h".strip()
    ok, msg = _run_shell(cmd, None, timeout=30)
    if ok or any(token in msg.lower() for token in ("usage", "dry_run", "output repository")):
        return True, phenv
    if "not found" in msg.lower():
        return False, (
            "playbooks_to_py3 is not installed on this SOAR build (common on 8.x). "
            "Delete Python 2.7 playbooks and re-import with Playbook Builder (metadata 3.13), "
            "or use Playbooks → Python update required in the SOAR UI."
        )
    return False, msg or "playbooks_to_py3 unavailable"


def phenv_path_candidates(slug: str, record_name: str = "") -> list[str]:
    """Build repo/playbook paths to try with playbooks_to_py3."""
    paths: list[str] = []
    name = (record_name or slug or "").strip().strip("/")
    slug = (slug or _scm_slug_from_record_name(name) or slug_from_label(name)).strip()
    for candidate in (
        f"local/{name}" if name else "",
        f"local/{slug}",
        name if name.startswith("local/") else "",
    ):
        candidate = candidate.strip()
        if candidate and candidate not in paths:
            paths.append(candidate)
    return paths


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    home = _phantom_home()
    env["PHANTOM_HOME"] = home
    env["PATH"] = f"{home}/bin:" + env.get("PATH", "")
    return env


def _run_shell(cmd: str, attempts_log: list[str] | None, timeout: int = 180) -> tuple[bool, str]:
    if attempts_log is not None:
        attempts_log.append(f"shell: {cmd}")
    try:
        proc = subprocess.run(
            ["/bin/bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/",
            env=_subprocess_env(),
        )
    except subprocess.SubprocessError as exc:
        return False, str(exc)
    output = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
    if attempts_log is not None:
        attempts_log.append(f"exit={proc.returncode} output={output[:500]!r}")
    if proc.returncode != 0:
        return False, output or f"exit {proc.returncode}"
    if "Successfully converted 0" in output:
        return False, output or "converted 0 playbooks"
    return True, output


def _current_user() -> str:
    try:
        import getpass
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return os.environ.get("USER") or os.environ.get("LOGNAME") or ""


def _phenv_command_prefix(use_sudo: bool = True) -> list[str]:
    """phenv must run as SOAR user ``phantom`` (Splunk requirement)."""
    if _current_user() == "phantom":
        return []
    if use_sudo:
        return ["sudo", "-n", "-u", "phantom"]
    return []


def _upgrade_via_mcp_bridge(
    slug: str,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> bool:
    """Ask MCP bridge (Mac + SSH key) to run phenv on SOAR when local phenv is blocked."""
    cfg = getattr(request, "_pb_config", None) or {}
    bridge = str(cfg.get("mcp_bridge_url") or "").strip().rstrip("/")
    if not bridge:
        return False
    base = bridge[:-6] if bridge.endswith("/agent") else bridge
    url = f"{base}/agent/api/upgrade-python39"
    body = json.dumps({"slug": slug}).encode("utf-8")
    if attempts_log is not None:
        attempts_log.append(f"bridge POST {url} slug={slug}")
    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        if attempts_log is not None:
            attempts_log.append(f"bridge upgrade failed: {exc}")
        return False
    if attempts_log is not None:
        attempts_log.append(f"bridge response: {str(payload)[:400]}")
    return isinstance(payload, dict) and payload.get("status") == "success"


def _run_phenv_convert(
    scm_path: str,
    request: Any | None = None,
    *,
    attempts_log: list[str] | None = None,
) -> tuple[bool, str]:
    """Run playbooks_to_py3 with wrapper, direct script, phenv, and sudo fallbacks."""
    cfg = _phenv_config(request)
    phenv = find_phenv(request)
    tool = find_playbooks_to_py3(request)
    prefix = _phenv_command_prefix(cfg["use_sudo"])
    path_q = shlex.quote(scm_path)
    commands: list[str] = []

    if PHENV_WRAPPER.is_file():
        commands.append(f"bash {shlex.quote(str(PHENV_WRAPPER))} {path_q} local")

    if tool:
        tool_q = shlex.quote(tool)
        py313 = shlex.quote(f"{_phantom_home()}/usr/python313/bin/python3.13")
        for core in (
            f"{tool_q} {path_q} local",
            f"{py313} {tool_q} {path_q} local",
            f"python3 {tool_q} {path_q} local",
        ):
            if prefix:
                pre = " ".join(shlex.quote(p) for p in prefix)
                commands.append(f"{pre} {core}")
            else:
                commands.append(core)

    if phenv:
        base = shlex.quote(phenv)
        core = f"{base} playbooks_to_py3 {path_q} local"
        if prefix:
            pre = " ".join(shlex.quote(p) for p in prefix)
            commands.append(f"{pre} {core}")
        else:
            commands.append(core)
        if cfg["use_sudo"] and prefix:
            commands.append(f"sudo -n {core}")  # fallback: sudo without -u if sudoers allows

    for cmd in commands:
        ok, msg = _run_shell(cmd, attempts_log)
        if ok:
            return True, msg

    available, status = phenv_tool_status(request)
    if not available:
        return False, status
    if not phenv and not PHENV_WRAPPER.is_file() and not tool:
        return False, "phenv not found (/opt/phantom/bin/phenv) and playbooks_to_py3 script missing"
    return False, msg if commands else "no phenv command candidates"


def _find_converted_playbook(
    slug: str,
    legacy_id: int | None,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> dict[str, Any] | None:
    slug = _scm_slug_from_record_name(slug) or slug_from_label(slug)
    for suffix in PHENV_SUFFIXES:
        found = find_playbook_by_slug(f"{slug}{suffix}", request)
        if found and not is_legacy_python27(found):
            return found

    slug_l = slug.lower()
    candidates: list[dict[str, Any]] = []
    for pb in _list_playbooks(request):
        if is_legacy_python27(pb):
            continue
        pid = int(pb.get("id") or 0)
        if legacy_id and pid == int(legacy_id):
            continue
        name = str(pb.get("name") or "").lower()
        if slug_l not in name:
            continue
        if any(name.endswith(s) or f"{s}/" in name for s in PHENV_SUFFIXES):
            candidates.append(pb)
        elif is_python_39(pb) and slug_l in name:
            candidates.append(pb)

    if not candidates:
        if attempts_log is not None:
            attempts_log.append(f"no converted playbook found for slug={slug}")
        return None

    candidates.sort(key=lambda p: p.get("id") or 0, reverse=True)
    return candidates[0]


def _rename_playbook(
    playbook_id: int,
    new_name: str,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> bool:
    from draft_import import _phantom_rest

    bodies = [
        {"name": new_name},
        {"playbook_name": new_name},
        {"name": new_name, "python_version": DEFAULT_PLAYBOOK_PYTHON_VERSION},
    ]
    for body in bodies:
        ok, resp, log = _phantom_rest(
            "POST",
            f"playbook/{playbook_id}",
            body,
            request=request,
        )
        if attempts_log is not None:
            attempts_log.extend(log)
            attempts_log.append(f"rename POST playbook/{playbook_id} -> {ok}")
        if ok:
            refreshed = _get_playbook_by_id(request, playbook_id)
            if refreshed and new_name.lower() in str(refreshed.get("name") or "").lower():
                return True
    return False


def _cleanup_stale_converted_copies(
    slug: str,
    keep_id: int,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> None:
    slug_l = slug.lower()
    for pb in _list_playbooks(request):
        pid = int(pb.get("id") or 0)
        if pid == keep_id or is_legacy_python27(pb):
            continue
        name = str(pb.get("name") or "").lower()
        if slug_l in name and any(s in name for s in PHENV_SUFFIXES):
            _delete_playbook(pid, request, attempts_log=attempts_log)


def upgrade_playbook_to_python3(
    slug: str,
    playbook_id: int | None,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
    keep_slug: bool = True,
) -> tuple[int | None, dict[str, Any] | None, list[str]]:
    """Convert a 2.7 classic playbook to Python 3 using phenv; delete the 2.7 copy."""
    log = attempts_log if attempts_log is not None else []
    slug = _scm_slug_from_record_name(slug) or slug_from_label(slug)
    legacy = _get_playbook_by_id(request, int(playbook_id)) if playbook_id else None
    if not legacy:
        legacy = find_playbook_by_slug(slug, request)
    if legacy and not is_legacy_python27(legacy):
        return int(legacy["id"]), legacy, log

    legacy_id = int(legacy["id"]) if legacy and legacy.get("id") is not None else playbook_id
    record_name = str((legacy or {}).get("name") or slug)

    phenv_ok = False
    phenv_msg = ""
    for scm_path in phenv_path_candidates(slug, record_name):
        phenv_ok, phenv_msg = _run_phenv_convert(scm_path, request, attempts_log=log)
        if phenv_ok:
            break

    if not phenv_ok:
        log.append(f"phenv failed: {phenv_msg[:400]}")
        if not _upgrade_via_mcp_bridge(slug, request, attempts_log=log):
            return legacy_id, legacy, log

    converted: dict[str, Any] | None = None
    for _ in range(PHENV_MAX_POLLS):
        converted = _find_converted_playbook(slug, legacy_id, request, attempts_log=log)
        if converted:
            break
        time.sleep(PHENV_POLL_SEC)

    if not converted or is_legacy_python27(converted):
        log.append("converted Python 3 playbook not found after phenv (expected *_py3)")
        return legacy_id, legacy, log

    converted_id = int(converted["id"])
    _pin_playbook_python_version(converted_id, request, attempts_log=log)

    if legacy_id and legacy_id != converted_id:
        _delete_playbook(int(legacy_id), request, attempts_log=log)
        time.sleep(0.5)

    final_record = converted
    final_id = converted_id
    if keep_slug:
        if _rename_playbook(converted_id, slug, request, attempts_log=log):
            time.sleep(0.5)
            renamed = find_playbook_by_slug(slug, request) or _get_playbook_by_id(request, converted_id)
            if renamed and not is_legacy_python27(renamed):
                final_record = renamed
                final_id = int(renamed["id"])
        _cleanup_stale_converted_copies(slug, final_id, request, attempts_log=log)

    _pin_playbook_python_version(final_id, request, attempts_log=log)
    final_record = _get_playbook_by_id(request, final_id) or final_record
    return final_id, final_record, log


def phenv_error_hint(attempts_log: list[str]) -> str:
    for line in reversed(attempts_log):
        if "phenv failed" in line or "exit=" in line or "shell:" in line:
            return line[:280]
    available, status = phenv_tool_status()
    if not available:
        return status
    return "phenv must run as user phantom — enable passwordless sudo: sudo -u phantom /opt/phantom/bin/phenv ..."


def ensure_playbook_python39(
    slug: str,
    playbook_id: int,
    request: Any | None,
    *,
    attempts_log: list[str] | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Ensure playbook is Python 3 — REST pin first, phenv on SOAR 6.x if still 2.7."""
    log = attempts_log if attempts_log is not None else []
    record = _get_playbook_by_id(request, playbook_id)
    if record and is_python_39(record):
        return playbook_id, record

    pinned = _pin_playbook_python_version(playbook_id, request, attempts_log=log)
    if pinned and is_python_39(pinned):
        return playbook_id, pinned

    record = _get_playbook_by_id(request, playbook_id) or record
    if record and not is_legacy_python27(record):
        return playbook_id, record

    new_id, new_record, _ = upgrade_playbook_to_python3(
        slug,
        playbook_id,
        request,
        attempts_log=log,
        keep_slug=True,
    )
    return new_id, new_record


def migrate_all_legacy_playbooks(
    request: Any | None,
    *,
    slugs: list[str] | None = None,
    repos: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Bulk-upgrade every Python 2.7 playbook (default: local repo)."""
    allowed_repos = {r.lower() for r in (repos or ["local"])}
    slug_filter = {s.lower() for s in slugs} if slugs else None

    rows = _list_playbooks(request)
    targets: list[dict[str, Any]] = []
    for pb in rows:
        if not is_legacy_python27(pb):
            continue
        name = str(pb.get("name") or "")
        repo = name.split("/")[0].lower() if "/" in name else "local"
        if repo not in allowed_repos and "local" not in allowed_repos:
            continue
        slug = _scm_slug_from_record_name(name) or slug_from_label(name)
        if slug_filter and slug.lower() not in slug_filter:
            continue
        targets.append(pb)

    results: list[dict[str, Any]] = []
    phenv_path = find_phenv(request)
    py3_tool = find_playbooks_to_py3(request)
    tool_ok, tool_status = phenv_tool_status(request)
    if dry_run:
        for pb in targets:
            results.append(
                {
                    "playbook_id": pb.get("id"),
                    "name": pb.get("name"),
                    "slug": _scm_slug_from_record_name(str(pb.get("name") or "")),
                    "action": "would_upgrade_phenv",
                    "python_version_before": python_version_value(pb),
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "dry_run": True,
            "count": len(results),
            "phenv_available": tool_ok,
            "phenv_path": phenv_path,
            "playbooks_to_py3": py3_tool,
            "phenv_tool_status": tool_status,
            "results": results,
            "content": f"Dry run: would upgrade **{len(results)}** Python 2.7 playbook(s) via phenv.",
        }

    upgraded = 0
    failed = 0
    for pb in sorted(targets, key=lambda r: int(r.get("id") or 0)):
        pid = int(pb["id"])
        name = str(pb.get("name") or "")
        slug = _scm_slug_from_record_name(name) or slug_from_label(name)
        attempts: list[str] = []
        new_id, new_record, _ = upgrade_playbook_to_python3(
            slug,
            pid,
            request,
            attempts_log=attempts,
            keep_slug=True,
        )
        ok = bool(new_record and not is_legacy_python27(new_record))
        if ok:
            upgraded += 1
        else:
            failed += 1
        results.append(
            {
                "playbook_id": pid,
                "new_playbook_id": new_id,
                "name": name,
                "slug": slug,
                "action": "upgraded" if ok else "upgrade_failed",
                "python_version_before": python_version_value(pb),
                "python_version_after": python_version_value(new_record),
                "playbook_search": playbook_search_term(
                    slug,
                    record_name=str((new_record or {}).get("name") or name),
                ),
                "ok": ok,
                "attempts": attempts[-8:],
                "error": phenv_error_hint(attempts) if not ok else "",
            }
        )

    return {
        "status": "success" if failed == 0 else "partial",
        "dry_run": False,
        "count": len(results),
        "upgraded": upgraded,
        "failed": failed,
        "phenv_available": tool_ok,
        "phenv_path": phenv_path,
        "playbooks_to_py3": py3_tool,
        "phenv_tool_status": tool_status,
        "results": results,
        "content": (
            f"Upgraded **{upgraded}** playbook(s) to Python 3"
            + (f"; **{failed}** failed." if failed else ".")
            + (
                f" phenv note: {tool_status}"
                if failed and not tool_ok
                else " Future imports auto-upgrade via phenv when SOAR REST pin is not enough."
            )
        ),
    }
