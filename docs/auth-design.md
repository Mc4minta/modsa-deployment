# MOD-SA: KMUTT OAuth2 login, design handout

**Status: DESIGN ONLY. Nothing here is implemented. Do not implement without owner approval.**
`CLAUDE.md` says: "KMUTT OAuth2 login is planned; do not implement it without an approved design."

This file is a self-contained handout for a Claude chat (or a new engineer) who has not seen
the repo. It explains what the system is **today**, what is decided, what is unknown, and the
proposed design. Facts marked **VERIFIED** were checked on the real VM; **UNKNOWN** and
`TODO(owner)` items must not be guessed. Never put secrets (client secret, session secret,
API keys, `.env` contents) in chat, commits or screenshots.

## 1. What MOD-SA is

KMUTT Student Affairs RAG chatbot. A student asks a question in Thai or English; the backend
retrieves matching chunks from ChromaDB and asks an LLM, returning `{answer, sources}`.
Answers must use retrieved context only. Public site:
`https://modsa.project.cpe.kmutt.ac.th/`.

## 2. Current architecture (production, after the frontend migration)

```text
Browser ──► https://modsa.project.cpe.kmutt.ac.th/
              ▼   (TODO(owner): where TLS terminates; how traffic reaches Nginx)
        Nginx container (port 80)
          ├─ /            static React build (SPA fallback to index.html)
          ├─ /assets/*    immutable cache
          └─ /api/*       allowlisted proxy to the backend
              ▼
        FastAPI backend container (port 8000, not published)
          ├─ ChromaDB (embedded, bind mount ./data/chroma)
          └─► outbound HTTPS: KMUTT CPE AI Gateway (OpenAI-compatible LLM + embeddings)
```

- Repo: `Mc4minta/modsa-deployment`. `main` is production. Work happens on `dev`.
- Stack: Docker Compose on one on-prem Ubuntu host. Services: `backend`, `nginx`
  (built from `nginx/Dockerfile`, which also builds the frontend), optional legacy `ngrok`
  (profile `tunnel`, being retired). Production start:
  `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
  (prod override publishes port 80; the local override binds `127.0.0.1:8080` for tests).
- Vercel and ngrok are retired or being retired (see `docs/MIGRATION-TODO.md`).
- The app currently has **no user accounts**, no database besides Chroma, no Redis.

### 2.1 Backend (`backend/`, FastAPI + LangChain + ChromaDB)

Layering (strict): `api/` → `services/` → `core/` | `pipeline/`. Keep `api/` thin; no
business logic there. Do not add `utils/`, `database/`, `models/` unless clearly needed.

- Routers in `backend/api/`: `chat.py` (`POST /chat/ask`), `health.py` (`GET /health`),
  `admin.py` (`POST /admin/reindex`, header `X-Admin-Key`). Included in `backend/main.py`;
  `CORSMiddleware` is configured from `CORS_ORIGINS`.
- Workflows in `backend/services/`: `rag_service.py`, `ingestion_service.py`.
- Settings in `backend/config.py` (`pydantic-settings`, read from `.env`; names are
  upper-case aliases such as `LLM_BASE_URL`, `CORS_ORIGINS`, `ADMIN_API_KEY`).
- Schemas in `backend/schemas/chat.py`.
- The backend does **not** know about the `/api` prefix: Nginx strips it
  (`/api/chat/ask` → `http://backend:8000/chat/ask`).
- Startup ingestion embeds ~1,233 chunks (71 files) through the gateway; skipped when the
  source manifest fingerprint is unchanged.

### 2.2 Nginx (`nginx/nginx.conf`)

- Exact-match allowlist for API routes: `GET|OPTIONS /api/health`,
  `POST|OPTIONS /api/chat/ask`. Everything else under `/api/` returns the JSON 404
  `{"detail":"Not found"}` (`location ^~ /api/`). `/docs`, `/openapi.json`, `/admin/*`
  are therefore unreachable from outside.
- Rate limits: chat 30 requests/min per IP (burst 10, nodelay), chat global 60/min
  (burst 20), health 60/min per IP. Limited requests return **429** (`limit_req_status 429`).
  Body limit 16 KiB. Proxy timeouts 10 s connect, 150 s read/send.
- JSON error pages for 404, 413, 429, 502, 503, 504, with `Access-Control-Allow-Origin: *`.
- Client IP uses `set_real_ip_from 172.28.0.0/16` + `X-Forwarded-For`
  (**TODO(owner)**: wrong value for real traffic; see Risks).
- Because `add_header` inside a location drops server-level headers, `X-Content-Type-Options:
  nosniff` is repeated in each location.

### 2.3 Frontend (`frontend/`, React 19 + TypeScript + Vite 8)

- Single page app, **no router library**. Chat UI. API client `frontend/src/services/api.ts`:
  base URL is `VITE_API_URL`, else `http://localhost:8000` in dev, else `/api`. The Docker build
  sets `VITE_API_URL=/api`. Calls `${API_URL}/chat/ask` and `${API_URL}/health` with `fetch`;
  45 s request timeout. Chat logic is in `src/hooks/useChatController.ts`.
- `cd frontend && npm ci && npm run check` = lint, typecheck, tests (vitest), build.

### 2.4 Verified facts (VERIFIED on the VM, 2026-11-22)

- Nginx serves `/` (200, `text/html`), assets, deep-route SPA fallback, JSON 404s for
  `/api/docs`, `/api/openapi.json`, `/api/admin/reindex`, 404 on `POST /api/health`, 413 on
  >16 KiB, and a real chat answer with 4 sources through `/api/chat/ask`.
- The built JS calls `/api` (no bare `/chat/ask`).
- One real chat request took ~37 s (frontend aborts at 45 s).
- During local testing Nginx saw clients as `172.28.0.1` (the Docker gateway).

## 3. Decisions already made (by the owner)

| Question | Decision |
|---|---|
| What needs login? | **Chat only.** The site shell and `/api/health` stay public. |
| Where does the session live? | **Backend cookie.** Backend runs the OAuth2 code flow and sets an HttpOnly cookie. Frontend never handles tokens. |
| Who may enter? | **Any KMUTT account** that completes login. |
| Provider details? | **Not yet requested** from KMUTT. |

## 4. Proposed design

### 4.1 Flow

```text
1. Browser loads /                      (public, static)
2. User clicks "Log in with KMUTT"  →   GET /api/auth/login
3. Backend creates state + nonce + PKCE verifier (kept in a short-lived signed cookie),
   302 → KMUTT authorize URL
4. User authenticates at KMUTT
5. KMUTT 302 → GET /api/auth/callback?code=…&state=…
6. Backend verifies state, exchanges code at the token endpoint (server side, client secret),
   validates the ID token (issuer, audience, nonce, signature via JWKS) or calls userinfo,
   builds the session, sets cookie, 302 → /
7. Frontend calls GET /api/auth/me → shows logged-in state
8. POST /api/chat/ask (cookie sent automatically, same origin)
     valid session → RAG as today;  missing/expired → 401 {"detail":"Not authenticated"}
9. POST /api/auth/logout clears the cookie (optionally calls the provider logout endpoint)
```

### 4.2 Backend changes (when approved)

- New `backend/api/auth.py` (thin routes) and `backend/services/auth_service.py` (flow logic).
  New schema file for the `/auth/me` response. Keep the layering rule.
- Routes (backend side, no `/api` prefix): `GET /auth/login`, `GET /auth/callback`,
  `POST /auth/logout`, `GET /auth/me`.
- A FastAPI dependency `require_user` applied to `POST /chat/ask` only. `/health` is public.
  `/admin/reindex` keeps `X-Admin-Key` and is still not exposed by Nginx.
- Library: `authlib` (OIDC client, PKCE, JWKS validation) rather than a hand-rolled flow.
  Pin the version in `requirements.txt`.
- Session: signed cookie via Starlette `SessionMiddleware` or `itsdangerous`. Contents: opaque
  user id (`sub`), display name if provided, `iat`, `exp`. No tokens, no chat text.
  Attributes: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, lifetime e.g. 8 h with an absolute
  maximum. `Lax` is required so the cookie survives the top-level redirect from KMUTT back to
  the callback. No server-side session store at this scale (stateless cookie).
- New settings in `backend/config.py` (names proposed): `AUTH_ENABLED` (default false so
  non-login deployments and tests keep working), `OIDC_ISSUER` (or explicit authorize/token/
  userinfo/JWKS URLs), `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_SCOPES`,
  `OIDC_REDIRECT_URI` (explicit, do not derive from the Host header), `SESSION_SECRET`,
  `SESSION_MAX_AGE_SECONDS`. Add placeholders to `.env.vm.example`, never real values.
- Open-redirect safety: after login only redirect to a fixed internal path.
- Logging: never log the code, tokens, cookie value or chat question with a user id unless a
  retention policy allows it.

### 4.3 Nginx changes (when approved)

- Add exact locations proxied to the backend, **before** the `^~ /api/` JSON-404 block:
  `GET /api/auth/login`, `GET /api/auth/callback`, `GET /api/auth/me`,
  `POST /api/auth/logout` → `http://backend:8000/auth/...`.
- Rate limit the new routes (a separate zone; callback and login are cheap but abusable).
- Pass `Host`, `X-Forwarded-For`, `X-Forwarded-Proto: https` so the backend builds correct
  URLs and sets `Secure` cookies. This depends on the TLS/proxy TODO below. Run uvicorn with
  proxy-header support limited to trusted proxy addresses.
- Keep the existing 16 KiB body limit and error pages. Make sure `Set-Cookie` and `Location`
  headers pass through. Do not cache auth responses (`Cache-Control: no-store`).
- With login in place, rate limiting can be keyed per user as well as per IP, which also
  softens the shared-IP problem behind a proxy.

### 4.4 Frontend changes (when approved)

- On load call `GET /api/auth/me`. If 401 on `/chat/ask`, show a "Log in with KMUTT" button
  (a plain link to `/api/auth/login`) and a clear Thai/English message instead of the generic
  error. Show a logout control when logged in.
- Add a `401` error code to `ApiError` mapping in `api.ts`; keep `credentials` default
  (same-origin sends cookies). Update i18n strings and tests.
- No tokens or user secrets in `localStorage`.

### 4.5 Security checklist

- Authorization-code flow + PKCE + `state` + `nonce`; exact redirect URI registered at KMUTT.
- Client secret only in server `.env` (mode 600), never in the frontend build or Git.
- Cookie flags as above; rotate `SESSION_SECRET` invalidates all sessions (acceptable).
- CSRF: `SameSite=Lax` plus `POST`-only state-changing routes and a JSON `Content-Type`
  requirement; revisit if any cross-origin client is added.
- CORS: same origin needs none; keep `CORS_ORIGINS` minimal (remove the old Vercel origin).
- Do not expose `/auth/*` beyond the four routes; keep the allowlist model.

## 5. Unknowns and blockers

Do not guess these:

1. **KMUTT provider details (not yet requested).** Ask KMUTT IT/SSO for:
   - OAuth2/OIDC client registration for `modsa.project.cpe.kmutt.ac.th`;
   - redirect URI to register: `https://modsa.project.cpe.kmutt.ac.th/api/auth/callback`;
   - client ID and secret; issuer URL or authorize, token, userinfo and JWKS endpoints;
   - allowed scopes and which claims are returned (student id, name, email, faculty);
   - PKCE support, token and session lifetimes, logout endpoint, single logout;
   - any approval or privacy policy required before handling student identifiers.
2. **TODO(owner): how traffic reaches Nginx and where TLS terminates.** Compose publishes
   port 80 only through the prod override. Secure cookies and the callback URL depend on this.
3. **TODO(owner): correct `set_real_ip_from`.** Currently trusts `172.28.0.0/16`. Wrong value
   means every user shares one rate-limit bucket, or `X-Forwarded-For` is spoofable.
4. **Privacy/retention:** which user claims may be stored; whether chat history per user is
   wanted (that would add a database and is out of scope for v1).
5. **Authorization beyond "any KMUTT account"** (for example students only) is undecided;
   design the check as configurable.

## 6. Suggested implementation plan (after approval)

1. Mock provider: run a local OIDC mock (for example a small `oidc-provider`/Keycloak-dev
   container, kept out of production compose) so the flow is built and tested without KMUTT.
2. Backend: config, `auth_service`, routes, `require_user` on `/chat/ask`, `AUTH_ENABLED`
   flag, unit tests with the mock. Verify `python -c "import main"` and the testing checklist
   in `CLAUDE.md`.
3. Nginx: add allowlisted auth locations and zones; validate with `nginx -t` in the image.
4. Frontend: `me` check, login button, 401 handling, i18n, tests; `npm run check`.
5. Verify end to end on the VM test port (`127.0.0.1:8080` via the local override) before
   touching production. Use a maintenance window; production is one live stack.
6. Switch to KMUTT provider values once registered; set `AUTH_ENABLED=true`.
7. Update `README.md`, `DEPLOYMENT.md` (env vars, callback URL, rollback = set
   `AUTH_ENABLED=false`).

## 7. Constraints for whoever continues

- Work on branch `dev`; do not touch `main`, do not force-push, never delete `archive/*` tags.
- The production VM is live: do not run `docker compose up/down/build/restart` there
  without a planned maintenance window. Test on the local override (`127.0.0.1:8080`).
- No CI and no automated backend test suite exist; verification is manual
  (curl smoke checks plus the checklist in `CLAUDE.md`).
- Related docs: `README.md`, `DEPLOYMENT.md` (runbook), `docs/MIGRATION-TODO.md`
  (cleanup checklist), `docs/backend-structure.md`, `CLAUDE.md`.

## 8. How to use this handout in Claude chat

Paste this file, then ask for one of: a review of the design; the request email/ticket text
for KMUTT IT; a Thai-language summary for stakeholders; a task breakdown; or the
implementation of a single step from section 6 once the owner has approved the design.
