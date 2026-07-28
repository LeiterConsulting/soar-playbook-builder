# Security policy

## Release status

SOAR Playbook Builder is currently an engineering alpha. It has not completed
live-platform authorization, multi-user isolation, import/run, resilience, or
production certification. Use it only in an isolated lab with test accounts and
non-production data.

Only the latest revision on `main` is eligible for security fixes during this
stage. No tagged version should be treated as a supported production release
until the trusted-release gates in
[`docs/TRUSTED_RELEASE_PLAN.md`](docs/TRUSTED_RELEASE_PLAN.md) are complete.

## Reporting a vulnerability

Use GitHub's **Security → Report a vulnerability** flow to open a private
security advisory for this repository. Include:

- the affected revision or package version;
- the vulnerable route, action, or component;
- reproduction steps using non-sensitive test data;
- impact and required privileges;
- relevant logs with credentials, tokens, case data, and internal hostnames
  removed.

Do not open a public issue containing exploit details, secrets, customer data,
or a working proof of concept before a fix is available. If private vulnerability
reporting is unavailable, open a public issue requesting a private contact
channel without including vulnerability details.

## Response process

Maintainers should acknowledge a private report, reproduce it in an isolated
environment, assign severity and reachability, and track remediation and
coordinated disclosure in the private advisory. Reachable critical and high
findings block release. Secrets exposed in logs or responses must be rotated in
addition to fixing the code path.

## Security expectations

- Leave Mode B disabled unless an authenticated, policy-compliant bridge is
  required.
- Use HTTPS and trusted certificates. Insecure transport settings are lab-only.
- Never use production SOAR tokens, cases, assets, or integrations for demos.
- Re-enter secrets manually during migration; configuration exports exclude
  them.
- Review generated playbooks and destructive-action confirmations before import
  or run.
- Treat action-policy log records as audit evidence only. Role enforcement is
  intentionally not enabled until the supported SOAR versions expose a verified
  authenticated principal/role contract to the REST handler.
