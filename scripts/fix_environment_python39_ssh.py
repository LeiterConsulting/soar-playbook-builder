#!/usr/bin/env python3
"""
Fix all Python 2.7 playbooks via SSH phenv (reliable on SOAR 6.x).

Uses REST to list/delete and SSH to SOAR host for phenv (same as manual fix).

Usage:
  ./scripts/fix-environment-python39.sh           # dry-run
  ./scripts/fix-environment-python39.sh --confirm
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from draft_import import is_legacy_python27, is_python_39, python_version_value  # noqa: E402


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def list_playbooks(client: httpx.Client) -> list[dict]:
    from soar_playbook_list import fetch_playbooks_httpx  # noqa: E402

    return fetch_playbooks_httpx(client)


def delete_playbook(client: httpx.Client, pid: int) -> bool:
    r = client.delete(f"/rest/playbook/{pid}")
    return r.status_code in (200, 204)


def slug_from_name(name: str) -> str:
    return name.split("/")[-1] if "/" in name else name


def phenv_ssh(slug: str, *, dry_run: bool) -> tuple[bool, str]:
    host = _env("SOAR_HOST", "10.236.39.108")
    user = _env("SSH_USER", "splunker")
    key = os.path.expanduser(_env("SSH_KEY", "~/Downloads/tylerkeypair.pem"))
    remote = (
        f"sudo -u phantom /opt/phantom/bin/phenv playbooks_to_py3 "
        f"local/{shlex.quote(slug)} local"
    )
    if dry_run:
        return True, f"would run: ssh {user}@{host} {remote}"
    cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
    if Path(key).is_file():
        cmd.extend(["-i", key])
    cmd.extend([f"{user}@{host}", remote])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = "\n".join(p for p in (proc.stdout, proc.stderr) if p).strip()
    ok = proc.returncode == 0 and "Successfully converted 0" not in out
    return ok, out or f"exit {proc.returncode}"


def find_py3_copy(client: httpx.Client, slug: str) -> dict | None:
    slug_l = slug.lower()
    matches = []
    for pb in list_playbooks(client):
        if is_legacy_python27(pb):
            continue
        name = str(pb.get("name") or "").lower()
        if slug_l in name and ("_py3" in name or is_python_39(pb)):
            matches.append(pb)
    if not matches:
        return None
    matches.sort(key=lambda p: p.get("id") or 0, reverse=True)
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    dry_run = not args.confirm

    url = _env("SOAR_URL", "https://10.236.39.108:8443")
    user = _env("SOAR_USER", "soar_local_admin")
    password = _env("SOAR_PASSWORD") or _env("SOAR_PASS")
    verify = _env("SOAR_VERIFY_SSL", "false").lower() in ("1", "true", "yes")

    if not password:
        print("Set SOAR_PASSWORD", file=sys.stderr)
        sys.exit(2)

    if dry_run:
        print("DRY RUN — pass --confirm to apply\n")

    with httpx.Client(base_url=url.rstrip("/"), auth=(user, password), verify=verify, timeout=60) as client:
        legacy = [pb for pb in list_playbooks(client) if is_legacy_python27(pb)]
        print(f"Found {len(legacy)} Python 2.7 playbook(s)\n")

        ok_count = fail_count = 0
        for pb in legacy:
            pid = int(pb["id"])
            name = str(pb.get("name") or "")
            slug = slug_from_name(name)
            py_before = python_version_value(pb)
            print(f"--- {name} (id {pid}, py={py_before})")

            ok, msg = phenv_ssh(slug, dry_run=dry_run)
            print(f"  phenv: {'OK' if ok else 'FAIL'} — {msg[:200]}")
            if not ok:
                fail_count += 1
                continue

            if dry_run:
                ok_count += 1
                continue

            time.sleep(2.0)
            converted = find_py3_copy(client, slug)
            if converted:
                print(f"  converted: {converted.get('name')} id={converted.get('id')} py={python_version_value(converted)}")
            else:
                print("  WARN: *_py3 copy not found in REST catalog yet")

            if delete_playbook(client, pid):
                print(f"  deleted legacy 2.7 id={pid}")
                ok_count += 1
            else:
                print(f"  WARN: could not delete legacy id={pid}")
                fail_count += 1

        print(f"\nDone: {ok_count} ok, {fail_count} failed")
        if not dry_run:
            print("Run: ./scripts/run-diagnose-python.sh")


if __name__ == "__main__":
    main()
