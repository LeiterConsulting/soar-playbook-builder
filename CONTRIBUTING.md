# Contributing

Thanks for improving SOAR Playbook Builder.

## Quick path

1. Fork [wts408/soar-playbook-builder](https://github.com/wts408/soar-playbook-builder) and create a branch from `main`.
2. Make focused changes; run tests before opening a PR:
   ```bash
   python3 -m pytest tests/ -q
   cd sidecar-ui && npm ci && npm run build
   ./package_app.sh
   ```
3. Open a pull request with a short summary, test plan, and SOAR version if behavior changed.

## Scope

- Keep PRs small and reviewable — one feature or fix per PR when possible.
- Do not commit credentials, `.env.local`, or `scripts/env.e2e.local`.
- Update [CHANGELOG.md](CHANGELOG.md) for user-visible changes.

## Questions

Open a GitHub issue for bugs or design discussion before large refactors.
