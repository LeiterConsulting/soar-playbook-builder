# E2E Validation Console

Interactive React UI for Playbook Builder end-to-end validation. Click **Validate entire app** or **Run this phase only**; results stream in real time with **Verify ↗** links to SOAR and the MCP bridge.

## Run

From `packaging/soar-playbook-builder-app`:

```bash
cp scripts/env.e2e.example scripts/env.e2e.local   # edit SOAR_URL, credentials, PB_ASSET
./scripts/run-e2e-console.sh
```

Open **http://127.0.0.1:5174**

The launcher starts:

1. Python API (`scripts/e2e_server.py`) on `:8765` — runs `e2e_validate.py`, SSE streaming
2. Vite dev server on `:5174` — proxies `/api` to the Python API

## Development

```bash
cd validation-console
npm install
npm run dev
```

In another terminal:

```bash
cd ..
uv run --with httpx --with starlette --with uvicorn python scripts/e2e_server.py
```

## Build static UI (optional)

```bash
npm run build
# output in validation-console/dist/
```

Production static hosting still needs the Python API on the same host (or configure CORS/proxy).

See [docs/E2E_VALIDATION.md](../docs/E2E_VALIDATION.md) for phase details and CLI-only mode.
