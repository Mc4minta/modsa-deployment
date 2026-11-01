# MOD-SA frontend

React + TypeScript + Vite chat client. This is an implemented application, not an empty scaffold.
See [root README](../README.md) for the backend and [graph quick start](../graph/QUICKSTART.md) for graph-only work.

## Local development

Use Node.js22 (22.17 tested) and npm. From this directory:

```sh
npm ci
cp .env.example .env
npm run dev
```

On PowerShell replace the copy command with `Copy-Item .env.example .env`.
Set `VITE_API_URL=http://localhost:8000`; start the backend separately. In production this must be the backend's HTTPS URL, not localhost. No secrets belong in VITE_* variables: they are bundled into the browser application.

## Verification

```sh
npm run check
```

Runs Oxlint, TypeScript, Vitest and production build. Tests use *.test.ts and *.test.tsx.
Production output is dist/. Check browser behavior at desktop/mobile widths separately; passing tests is not a visual or deployed end-to-end check.

## Integration

POST /chat/ask returns answer and sources. The deployed backend currently uses Vector RAG, not the standalone graph build. Set CORS_ORIGINS on the backend to the frontend origins. Configure the hosting service to build from frontend/ using npm run build and serve dist/. Do not assume an existing hosting deployment was updated by local code changes.
