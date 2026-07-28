#!/usr/bin/env python3
"""List SOAR playbooks and python_version — run before/after migration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from draft_import import (  # noqa: E402
    BUILDER_LABEL,
    is_legacy_python27,
    is_python_39,
    python_version_value,
    slug_from_label,
)


def _rows(resp) -> list[dict]:
    if isinstance(resp, list):
        return [r for r in resp if isinstance(r, dict)]
    if isinstance(resp, dict):
        for key in ("data", "playbooks", "items", "results"):
            data = resp.get(key)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
            if isinstance(data, dict) and data.get("id") is not None:
                return [data]
        if resp.get("id") is not None and resp.get("name"):
            return [resp]
    return []


from soar_playbook_list import fetch_playbooks_httpx, playbook_repo  # noqa: E402


def is_builder_playbook(record: dict) -> bool:
    labels = record.get("labels") or []
    tags = record.get("tags") or []
    if isinstance(labels, str):
        labels = [labels]
    if isinstance(tags, str):
        tags = [tags]
    label_blob = " ".join(str(x) for x in labels + tags).lower()
    desc = str(record.get("description") or "")
    return (
        BUILDER_LABEL in label_blob
        or "SOAR Playbook Builder" in desc
        or "playbook builder" in desc.lower()
    )


def playbook_slug(record: dict) -> str:
    name = str(record.get("name") or "")
    if "/" in name:
        return name.split("/")[-1]
    return slug_from_label(name) if name else ""


def _lookup_playbook_by_filter(client: httpx.Client, slug: str) -> list[dict]:
    """Best-effort search when catalog is small or names are SCM paths."""
    found: list[dict] = []
    for params in (
        {"_filter": f'name contains "{slug}"', "_page_size": 100},
        {"search": slug, "_page_size": 100},
        {"_page_size": 500, "_page": 1},
    ):
        try:
            r = client.get("/rest/playbook", params=params)
            if r.status_code != 200:
                continue
            for row in _rows(r.json()):
                hay = " ".join(
                    str(row.get(k) or "")
                    for k in ("name", "scm_path", "path", "description")
                ).lower()
                if slug.lower() in hay:
                    found.append(row)
        except Exception:
            continue
    return found


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> None:
    url = _env("SOAR_URL")
    user = _env("SOAR_USER")
    password = _env("SOAR_PASSWORD") or _env("SOAR_PASS")
    verify = _env("SOAR_VERIFY_SSL", "false").lower() in ("1", "true", "yes")
    if not url or not user or not password:
        print("Set SOAR_URL, SOAR_USER, SOAR_PASSWORD (scripts/env.e2e.local).", file=sys.stderr)
        sys.exit(2)

    with httpx.Client(
        base_url=url.rstrip("/"),
        auth=(user, password),
        verify=verify,
        timeout=60,
        trust_env=False,
    ) as client:
        version = "unknown"
        for ep in ("/rest/version", "/rest/system_info"):
            try:
                r = client.get(ep)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        version = (
                            data.get("version")
                            or data.get("product_version")
                            or data.get("platform_version")
                            or json.dumps(data)[:120]
                        )
                    break
            except Exception:
                pass

        playbooks = fetch_playbooks_httpx(client)
        builder = [pb for pb in playbooks if is_builder_playbook(pb)]
        local = [pb for pb in playbooks if playbook_repo(pb) == "local"]
        filter_hits: dict[str, list[dict]] = {}
        if not builder:
            for slug in ("hello_world", "servicenow_p1_incident", "aruba_clearpass_nac_quarantine"):
                hits = _lookup_playbook_by_filter(client, slug)
                if hits:
                    filter_hits[slug] = hits

    print(f"SOAR URL:     {url}")
    print(f"SOAR user:    {user}")
    print(f"SOAR version: {version}")
    print(
        f"Playbooks:    {len(playbooks)} total "
        f"({len(local)} local repo, {len(builder)} Playbook Builder tagged)\n"
    )

    if len(playbooks) <= 15 and not builder:
        print(
            "NOTE: If SOAR UI shows more playbooks, re-run after updating diagnose script "
            "(page_size=0 pagination fix).\n"
        )

    print(f"{'ID':>5}  {'PYTHON':<8}  {'REPO':<10}  {'STATUS':<12}  NAME")
    print("-" * 88)

    legacy = []
    show = sorted(playbooks, key=lambda x: (playbook_repo(x), str(x.get("name") or "")))
    if len(show) > 200:
        print(f"(Showing local + builder + legacy first; {len(show)} total)\n")
        priority = [
            pb for pb in show
            if playbook_repo(pb) == "local" or is_builder_playbook(pb) or is_legacy_python27(pb)
        ]
        show = priority + [pb for pb in show if pb not in priority]
        show = show[:200]

    for pb in show:
        pid = pb.get("id")
        name = pb.get("name") or ""
        repo = playbook_repo(pb)[:10]
        pyv = python_version_value(pb) or "?"
        tag = " [builder]" if is_builder_playbook(pb) else ""
        if is_python_39(pb):
            status = "ok (3.x)"
        elif is_legacy_python27(pb):
            status = "NEEDS FIX"
            legacy.append(name)
        else:
            status = "check"
        print(f"{pid:>5}  {pyv:<8}  {repo:<10}  {status:<12}  {name}{tag}")

    print()
    if not builder:
        print("Playbook Builder imports: NONE tagged in full catalog.")
        print("  Check local repo rows above (Repo=local). Your screenshot showed:")
        print("  aruba_clearpass_nac_quarantine — local, playbook_builder label, Python 2.")
        print("")
        for slug, extras in filter_hits.items():
            print(f"  Filter hit for {slug}: {len(extras)} row(s)")
            for row in extras[:3]:
                print(f"    id={row.get('id')} name={row.get('name')}")
        if filter_hits:
            print("")
    if legacy:
        print("Fix all at once from your Mac (repo scripts — NOT on SOAR SSH):")
        print("  cd ~/mcp-for-splunk/packaging/soar-playbook-builder-app")
        print("  ./scripts/fix-environment-python39.sh --confirm")
        print("")
        print("If playbooks_to_py3 exists on SOAR (SOAR 6.x / older 8.x), per-playbook on SOAR host:")
        print("  sudo find /opt/phantom -name 'playbooks_to_py3*' -type f")
        print("  sudo -u phantom /opt/phantom/bin/phenv playbooks_to_py3 -h   # NOT --help")
        print("")
        for name in legacy:
            repo_path = name if "/" in name else f"local/{name}"
            if not repo_path.startswith("local/"):
                repo_path = f"local/{repo_path.split('/')[-1]}"
            slug = repo_path.split("/")[-1]
            print(f"  sudo -u phantom /opt/phantom/bin/phenv playbooks_to_py3 {repo_path} local -d")
            print(f"  # dry-run; omit -d to convert -> {slug}_py3, then delete old 2.7 copy\n")
        print("On SOAR 8.x without playbooks_to_py3: delete 2.7 in Playbooks UI, re-import via Playbook Builder (Python 3.13).")
        print("Or: ./scripts/convert_playbooks_py3_ssh.sh " + " ".join(
            n.split("/")[-1] for n in legacy
        ))
    else:
        print("No Python 2.7 playbooks found.")


if __name__ == "__main__":
    main()
