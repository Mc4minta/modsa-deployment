# Frontend Hardening Validation Report

## Scope and repository state

- Branch: `refactor/frontend`
- Baseline HEAD: `0af2173b7b08fd529c146f9d3dc8bf50c372cc3f`
- Final HEAD: `0af2173b7b08fd529c146f9d3dc8bf50c372cc3f` (no commit created)
- Protected files preserved: untracked `AGENTS.md` and `docs/frontend-hardening-multi-agent-plan.md`.
- No branch switch, commit, push, deployment, secret access, Chroma mutation, or knowledge-data change was performed.

## Implemented changes

Frontend state is now reducer-backed through `src/hooks/useChatController.js`. Requests carry immutable request/chat IDs, are cancellable, timeout-aware, retryable, and reject late results. Drafts are memory-only and keyed by chat; completed messages only are persisted through bounded, versioned storage with corruption/quota recovery and clear-history support.

Markdown now uses `react-markdown`, GFM, and `rehype-sanitize`; only HTTP(S)/anchor URLs are clickable, tables use responsive wrappers, and sources present evidence coverage without confidence claims. Attachments were removed. Client/server guardrails trim and cap questions, reject obvious credentials/PEM keys, Thai sensitive terms, national IDs, and unknown request fields. Retrieved context is HTML-escaped before prompt interpolation and marked untrusted.

Accessibility work adds semantic history controls, focus trap/restore, Escape handling, live chat updates, reduced-motion scrolling, validated language state, UTF-8 Thai rendering, and mobile source/table wrapping.

## Files and dependencies

Changed frontend files include `App.jsx`, `App.css`, `ChatPanel.jsx`, `InputArea.jsx`, `LanguageSwitcher.jsx`, `MessageBubble.jsx`, `Sidebar.jsx`, `SourcesPanel.jsx`, language context/locales, API/storage utilities, Vite/Vitest config, and tests under `frontend/src/test/` and component test files. `frontend/src/utils/markdown.js` was removed after confirming no references. Added `frontend/scripts/mock-browser-api.mjs` provides deterministic browser fixtures.

Backend changes are limited to request schema validation, prompt/context hardening, the prompt-boundary wiring, and tests under `backend/tests/`.

Added runtime packages: `react-markdown`, `remark-gfm`, `rehype-sanitize`. Added test tooling: Vitest, Testing Library, jest-dom, and jsdom. The lockfile was regenerated once by the tooling workstream.

## Exact validation output

```text
npm ci
added 213 packages, audited 214 packages, found 0 vulnerabilities

npm run check
lint: exit 0 (3 existing Fast Refresh warnings)
Vitest: 7 files passed, 31 tests passed
Vite build: 284 modules; JS 395.36 kB (121.53 kB gzip); exit 0

python -c "import main"       exit 0 (backend venv)
python -m unittest discover -s tests -p "test_*.py"
...... / Ran 6 tests / OK

git diff --check               exit 0
```

## Browser validation matrix

`npx agent-browser` verified the Vite page loaded with meaningful content, no Vite error overlay, and an empty console error list. At 1440, 768, and 390 px, `document.documentElement.scrollWidth > window.innerWidth` was `false`. GFM Thai/English tables rendered semantically inside an overflow wrapper without page overflow; unsafe `javascript:` links rendered as text, safe source expansion opened correctly, and no-source fallback displayed its disclaimer. Thai switching set `document.documentElement.lang="th"`; keyboard drawer focus moved to close, Escape restored focus to the menu, and reduced-motion mode was exercised. Stop produced a retryable stopped message and a delayed response was rejected. Deterministic fixtures covered malformed payloads and HTTP 422/429/500, timeout, retry, no-source, unsafe URL, Thai text, and source/table rendering.

## Limitations and readiness

The local backend imported and passed its tests. A real known-topic POST was attempted against the local service and returned HTTP 500 because the environment reported no supported source files and has no configured model/data provider. This is an environment/data readiness blocker, not a frontend validation failure; no knowledge data was modified. Backend 500 responses still originate from the existing API error-detail path and should be sanitized in a separately approved backend security change.

The worktree remains intentionally uncommitted and contains the listed implementation files plus the preserved untracked owner files. The frontend hardening changes are ready for owner review and further integration, but are **not deployment-ready** until the backend knowledge/model provider is configured and the real known-topic request succeeds.
