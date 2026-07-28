#!/usr/bin/env python3
"""Smoke tests for ES ↔ SOAR ↔ Builder stitching (local + optional live SOAR)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "soar_playbook_builder"
sys.path.insert(0, str(APP_PY))

from sidecar_url import append_query, build_sidecar_query_params  # noqa: E402
from es_links import (  # noqa: E402
    attach_es_links,
    build_es_back_links,
    build_mission_control_url,
)
from investigation_context import hydrate_investigation_context, suggest_pattern_from_rule  # noqa: E402


class SmokeResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def ok(self, name: str) -> None:
        self.passed.append(name)

    def fail(self, name: str, detail: str) -> None:
        self.failed.append(f"{name}: {detail}")

    def skip(self, name: str, reason: str) -> None:
        self.skipped.append(f"{name}: {reason}")

    @property
    def success(self) -> bool:
        return not self.failed


def test_es_link_params(r: SmokeResult) -> None:
    pairs = build_sidecar_query_params(
        {"container_id": 99, "event_id": "ev-abc", "rule_name": "Failed Logins"}
    )
    url = append_query("https://soar/h/dir/asset/chat", pairs)
    if "container_id=99" in url and "event_id=ev-abc" in url:
        r.ok("es_link query params")
    else:
        r.fail("es_link query params", url)


def test_mission_control_url(r: SmokeResult) -> None:
    url = build_mission_control_url(
        "https://es.lab:8000",
        event_id="notable-event-123",
        rule_name="Failed Logins",
    )
    if not url or "ess_investigation" not in url or "event_id=notable-event-123" not in url:
        r.fail("mission control URL", str(url))
        return
    r.ok("mission control URL")


def test_investigation_context_es_links(r: SmokeResult) -> None:
    class _Req:
        GET = {}

    ctx = hydrate_investigation_context(
        _Req(),
        container_id=None,
        event_id="ev-smoke-1",
        rule_name="Failed Logins",
        es_web_url="https://es.example.com:8000",
    )
    if not ctx.get("es_back_url") or "ev-smoke-1" not in ctx["es_back_url"]:
        r.fail("investigation_context es_back_url", json.dumps(ctx, default=str))
        return
    if ctx.get("es_links", {}).get("mission_control"):
        r.ok("investigation_context es_links")
    else:
        r.fail("investigation_context es_links", "missing mission_control")


def test_pattern_suggestion(r: SmokeResult) -> None:
    pid = suggest_pattern_from_rule("Failed Logins - ES")
    if pid == "failed-logins-okta":
        r.ok("pattern suggestion from rule_name")
    else:
        r.fail("pattern suggestion", str(pid))


def test_utility_playbook_tgz(r: SmokeResult) -> None:
    tgz = ROOT / "dist" / "open_playbook_builder.tgz"
    if not tgz.is_file():
        r.skip("utility playbook tgz", f"missing {tgz} — run ./package_app.sh")
        return
    with tarfile.open(tgz, "r:gz") as tar:
        names = tar.getnames()
    if any(n.endswith("open_playbook_builder.py") for n in names):
        r.ok("utility playbook tgz structure")
    else:
        r.fail("utility playbook tgz", str(names))


def test_response_plan_template(r: SmokeResult) -> None:
    path = ROOT / "soar_content" / "response_plan_open_playbook_builder.json"
    if not path.is_file():
        r.fail("response plan template", "file missing")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("actions") and data["actions"][0].get("playbook_label") == "open_playbook_builder":
        r.ok("response plan template")
    else:
        r.fail("response plan template", "invalid actions")


def test_live_soar_es_link(r: SmokeResult) -> None:
    soar_url = os.environ.get("SOAR_URL", "").strip()
    if not soar_url:
        r.skip("live SOAR es_link", "SOAR_URL not set")
        return

    user = os.environ.get("SOAR_USER", "soar_local_admin")
    pwd = os.environ.get("SOAR_PASS", "password")
    asset = os.environ.get("ASSET", "mcpbridge")

    script = ROOT / "scripts" / "print_sidecar_url.sh"
    if not script.is_file():
        r.skip("live SOAR es_link", "print_sidecar_url.sh missing")
        return

    env = {**os.environ, "SOAR_URL": soar_url, "SOAR_USER": user, "SOAR_PASS": pwd, "ASSET": asset}
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        r.fail("live SOAR es_link", "print_sidecar_url.sh timed out")
        return

    if proc.returncode != 0:
        r.skip("live SOAR es_link", proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
        return

    es_link_line = ""
    for line in proc.stdout.splitlines():
        if "/es_link?" in line:
            es_link_line = line.strip()
            break
    if not es_link_line:
        r.fail("live SOAR es_link", "no es_link URL in print_sidecar_url output")
        return

    test_url = es_link_line.replace("EVENT_ID", "smoke-test-event").replace(
        "RULE_NAME", "Smoke%20Test"
    )
    test_url = test_url + ("&" if "?" in test_url else "?") + "format=json"

    import base64

    auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    req = Request(test_url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status not in (200, 302):
                r.fail("live SOAR es_link HTTP", f"status {resp.status}")
                return
            if "format=json" in test_url and "sidecar_url" not in body:
                r.fail("live SOAR es_link JSON", body[:300])
                return
            r.ok("live SOAR es_link")
    except HTTPError as exc:
        if exc.code in (401, 403):
            r.skip("live SOAR es_link HTTP", f"{exc.code} auth")
        else:
            r.fail("live SOAR es_link HTTP", f"{exc.code} {exc.reason}")
    except URLError as exc:
        r.skip("live SOAR es_link HTTP", str(exc.reason))


def main() -> int:
    r = SmokeResult()
    test_es_link_params(r)
    test_mission_control_url(r)
    test_investigation_context_es_links(r)
    test_pattern_suggestion(r)
    test_utility_playbook_tgz(r)
    test_response_plan_template(r)
    test_live_soar_es_link(r)

    print("=== Smoke test: ES ↔ SOAR ↔ Builder ===")
    for name in r.passed:
        print(f"  PASS  {name}")
    for name in r.skipped:
        print(f"  SKIP  {name}")
    for name in r.failed:
        print(f"  FAIL  {name}")

    print()
    print(f"Passed: {len(r.passed)}  Failed: {len(r.failed)}  Skipped: {len(r.skipped)}")
    return 0 if r.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
