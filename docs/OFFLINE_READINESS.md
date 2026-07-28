# Offline readiness and live-SOAR handoff

- **Snapshot:** 2026-07-28
- **Branch:** `codex/gate0-foundation`
- **Status:** offline trust core implemented; live import/run certification pending

Latest all-up offline run: **275 Python tests passed**, every evaluation suite
passed, **7 UI component/navigation tests and 4 Chromium tests passed**,
automated accessibility and three viewport targets passed, both production web
builds passed, and the final security/package gates below passed.

This is the boundary between work that can be proven from this repository and
work that would be speculation without an installed Splunk SOAR instance.

## Offline capability status

| Area | Offline result | Evidence | Live dependency |
|---|---|---|---|
| Playbook contract | Complete for IR 1.0 | Closed parser/schema/GBNF, bounded literals, typed nodes/bindings, graph validation | Migration compatibility on installed SOAR |
| Compiler | Complete for preview artifacts | Byte-deterministic Python + visual siblings, parity, hashes, round-trip and golden tests | Native VPE schema/import qualification |
| Preflight | Complete against supplied evidence | Closed GapReport; app/action/asset/parameter/datapath/permission/object/egress checks | Current installation evidence |
| No-model accuracy | Complete initial gate | 40/40 exact cases and all 31 deterministic gap IDs | Expand to 100+ reviewed full fixtures |
| Canonical templates | Complete initial library | 11/11 strict IR templates parse and dual-compile | Analyst/domain review and live runtime |
| Retrieval | Complete lexical baseline | Fixed 20-intent corpus; top-5 action recall 1.000; zero-network run | Real intent distribution and weakest-model tests |
| Model boundary | Complete provider/decoder contract | Constrained-output negotiation, strict TLS/address/size policy, bounded repair, adversarial scripted provider tests | Real local endpoint/model qualification |
| Organization templates | Strict path complete | Bounded duplicate-safe `custom_ir_templates_json`; exact ID binding; review-only UI | Migration of existing org content and live approval/import |
| Trusted review API/UI | Complete as review-only | IR/report/artifact hashes, blocked/clean states, explicit Import locked | Authenticated approval and commit-time revalidation |
| Legacy paths | Contained, not trusted | Bridge disabled when unset; legacy org Python ignored by default; Python 2 migration retired | Decide removal/migration timeline after inventory |
| Package/release | Complete offline gate | Deterministic archive, traversal/link/size/mode inspection, licenses, pinned Actions, checksums and UI SBOM | Clean install/upgrade/rollback |
| Dependency posture | Clean at snapshot | `pip-audit` and both `npm audit` runs report zero known vulnerabilities; Bandit high/medium gate passes | Re-run at every merge/release |
| UI | Core mock flow and trust states verified | Seven component/navigation tests plus four Chromium tests: clean/blocked review, four routes, axe, 1280/1440/1024 widths, console health, and zero external requests; Import/Run locked | SOAR proxy, supported-browser matrix, manual keyboard/screen-reader review, and analyst usability |

## Quality success criteria

| Quality | Offline success criterion | Current state | Required live closure |
|---|---|---|---|
| Functional | Every shipped template can be selected, strictly reviewed, preflighted, and preview-compiled without SOAR/model/network | Met | Install, import, open in VPE, and run |
| Secure | No reachable high dependency finding; high/medium SAST gate clean; fail-closed input/network/archive policies | Met for repository boundary | Principal/role authorization, CSRF/session, platform logs |
| Reliable | Same input/evidence/version produces byte-identical IR, report, artifacts, and package | Met | Restart/multi-worker and platform persistence |
| Resilient | Invalid model/config/index/archive/network responses return bounded stable failures and preserve last-good evidence | Met for covered fixtures | Timeout/restart/partial platform failures |
| Trustworthy | Every preview carries server-owned provenance and hashes; no baseline is represented as live evidence | Met | Actor approval and commit-time hash binding |
| Accurate | Exact expected gaps on 40 cases; 100% template compile; retrieval recall target met | Met for fixed corpora | Domain-reviewed workflows and runtime outputs |
| Stable | Full Python suite, all eval suites, both web builds, audits, and package inspection pass together | Met at snapshot; rerun before handoff | Supported SOAR/browser/version matrix |

## Trusted import remains intentionally disabled

An offline `gap_report.status=ok` means only that the supplied evidence and IR
are internally consistent. It is not permission to import. The review response
always carries:

```json
{
  "review_only": true,
  "import_enabled": false,
  "ready_for_import": false,
  "import_block_reason": "TRUSTED_IMPORT_DISABLED"
}
```

Do not remove that lock until the live gates in
[TRUSTED_REVIEW.md](./TRUSTED_REVIEW.md) and
[THREAT_MODEL.md](./THREAT_MODEL.md) pass.

## Handoff to the other machine

The installed UI is served by SOAR over its normal HTTPS endpoint. It does not
need a standalone Vite server or a `0.0.0.0` bind in production.

For local development only:

```bash
cd sidecar-ui
npm run dev:lan
```

That command binds Vite to `0.0.0.0`. Use it only on a trusted LAN/VPN, restrict
the host firewall to the development workstation, and never expose it directly
to the internet. The remote SOAR sidecar still needs the correct same-origin
handler URL and browser authentication.

When the live instance is available:

1. transfer and verify `dist/soar_playbook_builder.tgz`;
2. install it on a non-production SOAR 8.5.x instance;
3. create a test asset with Mode B and legacy Python disabled;
4. open the sidecar through SOAR HTTPS;
5. harvest the capability index and preserve its report;
6. run the read-only E2E phases first;
7. qualify native visual JSON with the Hello template;
8. enable isolated test import only after role/approval wiring exists;
9. run safe templates on disposable cases and assert outputs/cleanup;
10. proceed to integration/destructive tiers only with dedicated test assets.

## Offline verification commands

```bash
python3 -m compileall -q soar_playbook_builder tests scripts
python3 -m pytest -q tests
python3 soar_playbook_builder/eval/harness.py --suite all
cd sidecar-ui && npm ci && npx --no-install playwright install chromium
npm audit --audit-level=high && npm test && npm run test:e2e && npm run build
cd ../validation-console && npm ci && npm audit --audit-level=high && npm run build
cd ..
python3 -m pip_audit -r requirements.txt
python3 -m bandit -q -r soar_playbook_builder scripts -ll -ii
./package_app.sh
python3 scripts/inspect_app_archive.py dist/soar_playbook_builder.tgz
```
