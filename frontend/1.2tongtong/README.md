# MOD-SA Frontend 1.2 Tongtong

Production-oriented React/Vite client for the MOD-SA Student Affairs RAG API.
It preserves Wolf's visual direction while adding sanitized GFM tables, visible
evidence coverage, source metadata, privacy guardrails, resilient API states,
accessible navigation, bilingual UI, and automated tests.

## Local development

Requirements: Node.js `>=20.19.0` and the backend on port `8000`.

```powershell
Copy-Item .env.example .env
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Run the complete release gate with:

```powershell
npm run check
```

This runs Oxlint, Vitest, and a production Vite build. `VITE_API_URL` may be an
absolute API origin or `/api` behind a reverse proxy. Never put secrets in a
`VITE_*` variable because Vite embeds it in the browser bundle.

For UI testing without an LLM or vector database, run `npm run mock-api` in a
separate terminal. It serves deterministic bilingual table/source fixtures on
port `8000`; never use it as a production API.

## Deployment

For Docker, the repository Compose file builds this directory and Nginx proxies
`/api` to the backend:

```powershell
docker compose up --build
```

The UI is available at `http://localhost:5173`. For a static host, use this
directory as the project root, run `npm ci` then `npm run build`, publish
`dist/`, configure SPA fallback to `index.html`, and set `VITE_API_URL` to the
HTTPS backend origin. The included `vercel.json` provides fallback and security
headers for Vercel. Add the deployed frontend origin exactly to backend
`CORS_ORIGINS`.

Do not serve production with `vite preview`.
