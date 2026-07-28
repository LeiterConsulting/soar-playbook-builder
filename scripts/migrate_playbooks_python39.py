#!/usr/bin/env python3
"""
Bulk re-import Playbook Builder playbooks on Python 3.9 and remove stale copies.

Targets playbooks tagged ``playbook_builder`` (or created by the builder description).
Exports classic Python via REST, re-imports with 3.9 metadata + pylint header, then
optionally deletes builder playbooks still not on 3.9 and duplicate slugs.

Usage (dry-run — no changes):
  SOAR_URL=https://10.236.39.108:8443 SOAR_USER=admin SOAR_PASSWORD=*** \\
    python scripts/migrate_playbooks_python39.py

Apply changes:
  ... python scripts/migrate_playbooks_python39.py --confirm

Requires: httpx (pip install httpx)
"""

from __future__ import annotations

import argparse
import base64
import gzip
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from draft_import import (  # noqa: E402
    BUILDER_LABEL,
    DEFAULT_PLAYBOOK_PYTHON_VERSION,
    _import_api_succeeded,
    _normalize_playbook_source_for_import,
    _scm_slug_from_record_name,
    build_playbook_metadata,
    is_legacy_python27,
    is_python_39,
    package_source_with_metadata_b64,
    python_version_value,
    slug_from_label,
)


@dataclass
class MigrateResult:
    playbook_id: int
    name: str
    slug: str
    action: str
    detail: str = ""
    ok: bool = True


@dataclass
class MigrateReport:
    dry_run: bool
    results: list[MigrateResult] = field(default_factory=list)

    def add(self, **kwargs: Any) -> None:
        self.results.append(MigrateResult(**kwargs))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _client(url: str, user: str, password: str, verify: bool) -> httpx.Client:
    return httpx.Client(
        base_url=url.rstrip("/"),
        auth=(user, password),
        verify=verify,
        timeout=120.0,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        trust_env=False,
    )


def _rows(resp: Any) -> list[dict[str, Any]]:
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    if isinstance(resp, dict):
        for key in ("data", "playbooks", "items", "results"):
            data = resp.get(key)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
            if isinstance(data, dict) and data.get("id") is not None:
                return [data]
        if resp.get("id") is not None:
            return [resp]
    return []


def list_playbooks(client: httpx.Client) -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT))
    from soar_playbook_list import fetch_playbooks_httpx  # noqa: E402

    return fetch_playbooks_httpx(client)


def is_builder_playbook(record: dict[str, Any]) -> bool:
    labels = record.get("labels") or []
    tags = record.get("tags") or []
    if isinstance(labels, str):
        labels = [labels]
    if isinstance(tags, str):
        tags = [tags]
    desc = str(record.get("description") or "")
    name = str(record.get("name") or "").lower()
    return (
        BUILDER_LABEL in labels
        or BUILDER_LABEL in tags
        or "SOAR Playbook Builder" in desc
        or "playbook builder" in desc.lower()
        or name.endswith("_incident")
        or "servicenow" in name
        or "hello_world" in name
    )


def find_playbook_by_slug(client: httpx.Client, slug: str) -> dict[str, Any] | None:
    slug_l = slug.lower()
    matches: list[dict[str, Any]] = []
    for pb in list_playbooks(client):
        if playbook_slug(pb).lower() == slug_l:
            matches.append(pb)
        elif slug_l in str(pb.get("name") or "").lower():
            matches.append(pb)
    if not matches:
        return None
    matches.sort(key=lambda r: (not is_python_39(r), -(int(r.get("id") or 0))))
    return matches[0]


def playbook_slug(record: dict[str, Any]) -> str:
    name = str(record.get("name") or "")
    return _scm_slug_from_record_name(name) or slug_from_label(name)


def decode_export_b64(playbook_b64: str) -> str:
    raw = base64.b64decode(playbook_b64)
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tar:
        py_members = [m for m in tar.getmembers() if m.name.endswith(".py")]
        py_members.sort(key=lambda m: len(m.name))
        for member in py_members:
            fh = tar.extractfile(member)
            if not fh:
                continue
            text = fh.read().decode("utf-8", errors="replace").strip()
            if "def on_start" in text:
                return text
        for member in py_members:
            fh = tar.extractfile(member)
            if fh:
                return fh.read().decode("utf-8", errors="replace").strip()
    return ""


def export_playbook_source(client: httpx.Client, playbook_id: int) -> str:
    r = client.get(f"/rest/playbook/{playbook_id}", params={"playbook_export": True})
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            if data.get("playbook"):
                src = decode_export_b64(str(data["playbook"]))
                if src:
                    return src
            for key in ("python", "code", "source"):
                val = data.get(key)
                if isinstance(val, str) and "def on_start" in val:
                    return val.strip()

    r2 = client.get(f"/rest/playbook/{playbook_id}/export")
    if r2.status_code == 200:
        data = r2.json()
        if isinstance(data, dict) and data.get("playbook"):
            src = decode_export_b64(str(data["playbook"]))
            if src:
                return src

    r3 = client.get(f"/rest/playbook/{playbook_id}")
    if r3.status_code == 200:
        data = r3.json()
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            for key in ("python", "code", "source"):
                val = data.get(key)
                if isinstance(val, str) and "def on_start" in val:
                    return val.strip()
    return ""


def local_scm_id(client: httpx.Client) -> int:
    r = client.get("/rest/scm")
    r.raise_for_status()
    rows = _rows(r.json())
    for row in rows:
        name = str(row.get("name") or "").lower()
        if name in {"local", "default"}:
            return int(row["id"])
    for row in rows:
        if row.get("id") is not None:
            return int(row["id"])
    return 2


def import_playbook(client: httpx.Client, b64: str, scm_id: int) -> tuple[bool, Any]:
    bodies = [
        {"playbook": b64, "scm_id": scm_id, "force": True},
        {"playbook": b64, "scm": "local", "scm_id": scm_id, "force": True},
    ]
    last: Any = None
    for body in bodies:
        r = client.post("/rest/import_playbook", json=body)
        if r.status_code >= 400:
            last = r.text[:300]
            continue
        resp = r.json()
        if _import_api_succeeded(resp):
            return True, resp
        last = resp
    return False, last


def pin_python_version(client: httpx.Client, playbook_id: int) -> bool:
    candidates: list[Any] = [DEFAULT_PLAYBOOK_PYTHON_VERSION, "3", 3.9, 3]
    for candidate in candidates:
        r = client.post(
            f"/rest/playbook/{playbook_id}",
            json={"python_version": candidate},
        )
        if r.status_code >= 400:
            continue
        refreshed = get_playbook(client, playbook_id)
        if refreshed and is_python_39(refreshed):
            return True
    return False


def get_playbook(client: httpx.Client, playbook_id: int) -> dict[str, Any] | None:
    r = client.get(f"/rest/playbook/{playbook_id}")
    if r.status_code != 200:
        return None
    rows = _rows(r.json())
    return rows[0] if rows else None


def delete_playbook(client: httpx.Client, playbook_id: int) -> bool:
    r = client.delete(f"/rest/playbook/{playbook_id}")
    return r.status_code in (200, 204)


def display_name_from_record(record: dict[str, Any]) -> str:
    name = str(record.get("name") or "Playbook")
    if "/" in name:
        slug = playbook_slug(record)
        return slug.replace("_", " ").title()
    return name.replace("_", " ").title() if name.islower() else name


def reimport_playbook(
    client: httpx.Client,
    record: dict[str, Any],
    *,
    dry_run: bool,
    scm_id: int,
    report: MigrateReport,
) -> int | None:
    pid = int(record["id"])
    slug = playbook_slug(record)
    name = display_name_from_record(record)
    py_before = python_version_value(record)
    legacy = is_legacy_python27(record)

    if dry_run:
        action = "would_delete_and_reimport" if legacy else "would_reimport"
        report.add(
            playbook_id=pid,
            name=str(record.get("name") or ""),
            slug=slug,
            action=action,
            detail=f"python_version={py_before or 'unknown'} -> {DEFAULT_PLAYBOOK_PYTHON_VERSION}",
        )
        return pid

    source = export_playbook_source(client, pid)
    if not source:
        report.add(
            playbook_id=pid,
            name=str(record.get("name") or ""),
            slug=slug,
            action="reimport_skipped",
            detail="Could not export Python source",
            ok=False,
        )
        return None

    if legacy:
        if not delete_playbook(client, pid):
            report.add(
                playbook_id=pid,
                name=str(record.get("name") or ""),
                slug=slug,
                action="delete_before_reimport_failed",
                detail=f"python_version={py_before}",
                ok=False,
            )
            return None
        time.sleep(1.5)

    source = _normalize_playbook_source_for_import(source)
    meta = build_playbook_metadata(name, pattern=slug.replace("-", "_"))
    b64 = package_source_with_metadata_b64(source, slug, meta)
    ok, resp = import_playbook(client, b64, scm_id)
    if not ok:
        report.add(
            playbook_id=pid,
            name=str(record.get("name") or ""),
            slug=slug,
            action="reimport_failed",
            detail=str(resp)[:240],
            ok=False,
        )
        return None

    time.sleep(2.0)
    refreshed = find_playbook_by_slug(client, slug)
    if not refreshed:
        refreshed = get_playbook(client, pid) if not legacy else None
    if not refreshed:
        report.add(
            playbook_id=pid,
            name=str(record.get("name") or ""),
            slug=slug,
            action="reimport_resolve_failed",
            detail="Import succeeded but playbook not found by slug",
            ok=False,
        )
        return None

    new_pid = int(refreshed["id"])
    pin_python_version(client, new_pid)
    time.sleep(0.5)
    refreshed = get_playbook(client, new_pid) or refreshed
    py_after = python_version_value(refreshed)

    report.add(
        playbook_id=new_pid,
        name=str(refreshed.get("name") or ""),
        slug=slug,
        action="reimported",
        detail=f"python_version {py_before or '?'} -> {py_after or DEFAULT_PLAYBOOK_PYTHON_VERSION}",
        ok=is_python_39(refreshed),
    )
    return new_pid


def run_phenv_on_soar_host(
    slugs: list[str],
    *,
    dry_run: bool,
    report: MigrateReport,
) -> None:
    """Convert 2.7 classics via Splunk's phenv playbooks_to_py3 (required on SOAR 6.x)."""
    host = _env("SOAR_HOST") or _env("SOAR_URL", "").replace("https://", "").replace("http://", "").split(":")[0]
    ssh_user = _env("SSH_USER", "splunker")
    ssh_key = _env("SSH_KEY", str(Path.home() / "Downloads/tylerkeypair.pem"))
    if not host:
        print("Set SOAR_HOST for --phenv-ssh", file=sys.stderr)
        return

    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
    if Path(ssh_key).is_file():
        ssh_base.extend(["-i", ssh_key])

    for slug in slugs:
        remote_cmd = f"sudo -u phantom /opt/phantom/bin/phenv playbooks_to_py3 local/{slug} local"
        if dry_run:
            report.add(
                playbook_id=0,
                name=slug,
                slug=slug,
                action="would_phenv_ssh",
                detail=remote_cmd,
            )
            continue
        proc = subprocess.run(
            [*ssh_base, f"{ssh_user}@{host}", remote_cmd],
            capture_output=True,
            text=True,
        )
        detail = (proc.stdout or proc.stderr or "").strip()[:240]
        report.add(
            playbook_id=0,
            name=slug,
            slug=slug,
            action="phenv_ssh",
            detail=detail or f"exit {proc.returncode}",
            ok=proc.returncode == 0,
        )


def dedupe_builder_slugs(
    client: httpx.Client,
    playbooks: list[dict[str, Any]],
    *,
    dry_run: bool,
    report: MigrateReport,
) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pb in playbooks:
        if not is_builder_playbook(pb):
            continue
        groups[playbook_slug(pb)].append(pb)

    for slug, rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: (not is_python_39(r), -(int(r.get("id") or 0))))
        keep = rows[0]
        for dup in rows[1:]:
            pid = int(dup["id"])
            if dry_run:
                report.add(
                    playbook_id=pid,
                    name=str(dup.get("name") or ""),
                    slug=slug,
                    action="would_delete_duplicate",
                    detail=f"keep id {keep.get('id')} ({python_version_value(keep)})",
                )
                continue
            if delete_playbook(client, pid):
                report.add(
                    playbook_id=pid,
                    name=str(dup.get("name") or ""),
                    slug=slug,
                    action="deleted_duplicate",
                    detail=f"kept id {keep.get('id')}",
                )
            else:
                report.add(
                    playbook_id=pid,
                    name=str(dup.get("name") or ""),
                    slug=slug,
                    action="delete_duplicate_failed",
                    detail=f"kept id {keep.get('id')}",
                    ok=False,
                )


def delete_non_39_builder(
    client: httpx.Client,
    playbooks: list[dict[str, Any]],
    *,
    dry_run: bool,
    report: MigrateReport,
) -> None:
    for pb in playbooks:
        if not is_builder_playbook(pb):
            continue
        if is_python_39(pb):
            continue
        pid = int(pb["id"])
        slug = playbook_slug(pb)
        if dry_run:
            report.add(
                playbook_id=pid,
                name=str(pb.get("name") or ""),
                slug=slug,
                action="would_delete_non_39",
                detail=f"python_version={python_version_value(pb)}",
            )
            continue
        if delete_playbook(client, pid):
            report.add(
                playbook_id=pid,
                name=str(pb.get("name") or ""),
                slug=slug,
                action="deleted_non_39",
                detail=f"python_version={python_version_value(pb)}",
            )
        else:
            report.add(
                playbook_id=pid,
                name=str(pb.get("name") or ""),
                slug=slug,
                action="delete_non_39_failed",
                detail=f"python_version={python_version_value(pb)}",
                ok=False,
            )


def run_migration(args: argparse.Namespace) -> MigrateReport:
    url = args.soar_url or _env("SOAR_URL")
    user = args.soar_user or _env("SOAR_USER")
    password = args.soar_password or _env("SOAR_PASSWORD") or _env("SOAR_PASS")
    verify = args.verify_ssl if args.verify_ssl is not None else _env("SOAR_VERIFY_SSL", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    if not url or not user or not password:
        print("Set SOAR_URL, SOAR_USER, SOAR_PASSWORD (or pass flags).", file=sys.stderr)
        sys.exit(2)

    dry_run = not args.confirm
    report = MigrateReport(dry_run=dry_run)

    with _client(url, user, password, verify) as client:
        playbooks = list_playbooks(client)
        builder = [pb for pb in playbooks if is_builder_playbook(pb)]
        print(f"Found {len(playbooks)} playbook(s); {len(builder)} Playbook Builder tagged.")

        targets = builder
        if args.slugs:
            slug_set = {s.lower() for s in args.slugs}
            targets = [pb for pb in playbooks if playbook_slug(pb).lower() in slug_set]
        elif not args.force_all:
            targets = [pb for pb in builder if not is_python_39(pb)]

        scm_id = local_scm_id(client)
        for pb in sorted(targets, key=lambda r: int(r.get("id") or 0)):
            reimport_playbook(client, pb, dry_run=dry_run, scm_id=scm_id, report=report)

        if not dry_run:
            time.sleep(2.0)
            playbooks = list_playbooks(client)

        if args.dedupe:
            dedupe_builder_slugs(client, playbooks, dry_run=dry_run, report=report)
            if not dry_run:
                time.sleep(1.0)
                playbooks = list_playbooks(client)

        if args.delete_non_39:
            delete_non_39_builder(client, playbooks, dry_run=dry_run, report=report)

        if args.phenv_ssh:
            still_legacy = [
                playbook_slug(pb)
                for pb in playbooks
                if is_legacy_python27(pb)
                and (not args.slugs or playbook_slug(pb).lower() in {s.lower() for s in args.slugs})
            ]
            still_legacy = sorted(set(still_legacy))
            if still_legacy:
                print(f"Running phenv playbooks_to_py3 for: {', '.join(still_legacy)}")
                run_phenv_on_soar_host(still_legacy, dry_run=dry_run, report=report)

    return report


def print_report(report: MigrateReport) -> None:
    mode = "DRY RUN" if report.dry_run else "APPLIED"
    print(f"\n=== Migration report ({mode}) ===")
    for row in report.results:
        flag = "OK" if row.ok else "FAIL"
        print(f"[{flag}] {row.action:24} id={row.playbook_id:4} slug={row.slug:24} {row.name}")
        if row.detail:
            print(f"       {row.detail}")

    actions = {}
    for row in report.results:
        actions[row.action] = actions.get(row.action, 0) + 1
    print("\nSummary:", json.dumps(actions, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soar-url", default="", help="SOAR base URL (or SOAR_URL env)")
    parser.add_argument("--soar-user", default="", help="SOAR REST user (or SOAR_USER env)")
    parser.add_argument("--soar-password", default="", help="SOAR REST password")
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        default=None,
        help="Verify TLS certificates (default: false)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apply re-imports and deletions (default is dry-run only)",
    )
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        dest="slugs",
        metavar="SLUG",
        help="Migrate only this slug (repeatable), e.g. --slug servicenow_p1_incident",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Re-import all builder playbooks, even if already on 3.9",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        default=True,
        help="Delete duplicate builder slugs, keeping newest 3.9 copy (default: on)",
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Skip duplicate slug cleanup",
    )
    parser.add_argument(
        "--delete-non-39",
        action="store_true",
        default=False,
        help="Delete builder playbooks still not on 3.9 after re-import (dangerous on SOAR 6.x — use --phenv-ssh instead)",
    )
    parser.add_argument(
        "--no-delete-non-39",
        action="store_true",
        help="Skip deleting playbooks still not on 3.9 (default)",
    )
    parser.add_argument(
        "--phenv-ssh",
        action="store_true",
        help="After REST re-import, run phenv playbooks_to_py3 on SOAR host via SSH for playbooks still on 2.7",
    )
    args = parser.parse_args()
    if args.no_dedupe:
        args.dedupe = False
    if args.no_delete_non_39:
        args.delete_non_39 = False

    if args.no_delete_non_39:
        args.delete_non_39 = False

    if not args.confirm:
        print("Dry run — no SOAR changes. Pass --confirm to apply.")
        print("Note: SOAR 6.x classic playbooks stay on Python 2.7 after REST re-import.")
        print("      Use --phenv-ssh (or scripts/convert_playbooks_py3_ssh.sh) on the SOAR host.\n")

    report = run_migration(args)
    print_report(report)
    failed = [r for r in report.results if not r.ok]
    sys.exit(1 if failed and args.confirm else 0)


if __name__ == "__main__":
    main()
