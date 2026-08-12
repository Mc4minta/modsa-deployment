# MOD-SA Frontend Hardening: Multi-Agent Execution Plan

## Control Block

- **Execution status:** `PLAN_ONLY`
- **Target branch:** `refactor/frontend`
- **Audited baseline:** `0af2173`
- **Primary target:** `frontend/`
- **Allowed backend support:** request validation, RAG prompt hardening, and tests only
- **Forbidden without owner approval:** commit, push, deploy, branch switching, secrets, Chroma/data mutation

Luna High must act as the root orchestrator. Read root `AGENTS.md` and this document before delegating. While status is `PLAN_ONLY`, agents may inspect and report only. Begin edits only after the owner supplies `APPROVE EXECUTION`. Preserve the existing untracked `AGENTS.md` and all unrelated user changes.

## Objective

Deliver a secure, grounded, bilingual React/Vite chat frontend with:

- sanitized GFM Markdown and responsive tables;
- honest evidence/source presentation;
- client and server guardrails;
- race-safe chat, request, draft, and persistence state;
- accessible desktop/mobile behavior;
- automated tests and reproducible validation.

The backend contract remains `POST /chat/ask` with `{ "question": "..." }`, returning `{ "answer": string, "sources": array }`. Do not expose attachment controls until an upload API exists. Do not describe source count as answer correctness or confidence.

## Confirmed Baseline Findings

1. The regex Markdown renderer does not support tables and can generate unsafe `javascript:` links before rendering through `dangerouslySetInnerHTML`.
2. File selection is visible but files are discarded because the API accepts only `question`.
3. The UI expects `confidence`, but the backend does not return it; sourced answers are therefore mislabeled low confidence.
4. `messages`, `sessionId`, `isLoading`, and `chatList` are independent states. A response started in chat A can be appended and persisted in chat B after new/select/delete navigation.
5. A module-global `AbortController` can be cleared by the wrong request. There is no timeout, response normalization, or useful error taxonomy.
6. Draft, attachment, and voice state are not session-aware. Chat storage has no schema version, validation, limits, or visible quota failure.
7. There are no frontend test files or `check` script. `node_modules/` is absent.
8. Repository text is valid UTF-8 and `index.html` declares UTF-8. Treat visible mojibake as a transport, upstream-data, or font issue until browser/network evidence proves otherwise.

## Target State Invariants

- Every request has immutable `requestId` and `chatId` ownership.
- New/select/delete chat cancels the active request; late results are ignored.
- `isLoading` and chat summaries are derived, not separately synchronized.
- Messages have `pending`, `success`, `error`, or `stopped` status.
- Drafts are isolated per chat and remain memory-only by default.
- Only validated, serializable, completed state is persisted.
- Storage is versioned, bounded, recoverable from corrupt data, and reports quota failure.
- One global request may run at a time unless the owner explicitly approves background per-chat requests.

Recommended implementation: a `useChatController` hook backed by `useReducer`. Keep `AbortController` in a ref; reducer state stores only IDs and status. Initialize chats once from a versioned storage adapter, derive the sidebar list from reducer state, and persist completed snapshots after state transitions.

## Parallel Execution Waves

### Wave 0 — Root Orchestrator: Baseline Gate

1. Confirm branch and worktree with `git status --short --branch`.
2. Record current HEAD and preserve unrelated changes.
3. Run `npm ci` only after approval; record any lockfile failure before changing it.
4. Capture baseline lint/build output and desktop/mobile screenshots when runnable.
5. Create a shared issue checklist; do not let agents edit the same files concurrently.

### Wave 1 — Three Parallel Implementation Agents

#### Agent A: State, Requests, and Persistence

Owns `App.jsx`, `services/api.js`, `utils/storage.js`, new chat-controller hooks/reducer, and their tests.

- Implement request/session identity, cancellation, timeout, normalized responses, typed error codes, and stale-result rejection.
- Use same-origin API fallback in production and localhost only in development.
- Derive loading and sidebar summaries from canonical chat state.
- Add versioned storage validation, bounds, migration/fallback, clear-history behavior, and storage-error reporting.
- Ensure new/select/delete/stop and reload transitions are deterministic.

#### Agent B: Safe Rendering, Tables, and Evidence

Owns `MessageBubble.jsx`, `SourcesPanel.jsx`, Markdown/source CSS sections, and rendering tests.

- Replace the regex renderer with `react-markdown`, `remark-gfm`, and `rehype-sanitize`.
- Permit only `http:`, `https:`, and safe anchors; invalid URLs render as text.
- Wrap semantic tables in an overflow container; support Thai wrapping, code blocks, lists, and mobile widths.
- Replace confidence language with evidence coverage based on verified source presence/count, including a no-source state and disclaimer.
- Remove `dangerouslySetInnerHTML`; remove `utils/markdown.js` only when unused.

#### Agent C: Input and Server Guardrails

Owns `InputArea.jsx`, new `utils/guards.js`, backend `schemas/chat.py`, `prompts/rag_prompt.py`, and focused tests.

- Trim input and enforce a 1,500-character limit on client and server.
- Block or warn on obvious secrets, passwords, API keys, Thai sensitive-data terms, and 13-digit national IDs with precise bilingual messages.
- Remove attachment state and controls. Keep voice only when supported, use the selected language, and clean it up correctly.
- Make Enter composition-safe.
- Tell the model to treat retrieved content as untrusted data, ignore embedded instructions, avoid invented facts/contacts, cite evidence, and use tables only for genuinely tabular comparisons.

### Wave 2 — Two Parallel Integration Agents

#### Agent D: Accessibility and Interaction

Runs after Wave 1 UI changes. Owns `Sidebar.jsx`, `ChatPanel.jsx`, language components, `index.html`, and remaining UI CSS.

- Add keyboard-operable history, unique IDs, focus management, Escape handling, `aria-live`, reduced-motion behavior, and functional state toggles.
- Sync validated language state to `document.documentElement.lang`.
- Prevent forced auto-scroll when the reader has moved away from the bottom.
- Verify drawer and composer behavior at 390, 768, and 1440 px.

#### Agent E: Tooling and Test Harness

Owns `package.json`, `package-lock.json`, Vite/Vitest configuration, shared test setup, and mock API tooling.

- Add Testing Library/Vitest and a single `npm run check` gate: lint, tests, build.
- Regenerate the lockfile only once and only in this workstream.
- Provide deterministic API fixtures for success, no sources, malformed response, 401/422/429/500, timeout, abort, unsafe URL, Markdown table, and Thai text.

Each primary agent may spawn one **read-only** sub-agent for adversarial test design. Only the primary owner edits its files. Every agent returns: files changed, invariants addressed, commands run, results, and unresolved risks.

### Wave 3 — Parallel Read-Only Review

- **State reviewer:** replay navigation, cancellation, reload, rapid-send, and corrupt-storage scenarios.
- **Security reviewer:** attempt HTML/script injection, unsafe protocols, prompt injection, sensitive input, and malformed API payloads.
- **UX reviewer:** inspect Thai/English text, tables, sources, keyboard flow, mobile overflow, and reduced motion.

Reviewers do not patch. The root orchestrator assigns follow-up fixes to the relevant file owner, then reruns the full gate.

## Required Acceptance Matrix

| Area | Required proof |
|---|---|
| State isolation | A response from chat A never appears in chat B; late results after cancel are ignored |
| Recovery | Stop, error, reload, corrupt storage, and quota failure produce explicit non-stuck states |
| Markdown security | Script/event-handler HTML is inert; `javascript:` and malformed source URLs are not clickable |
| Tables | Valid GFM renders a semantic table; 390 px viewport scrolls the table without page overflow |
| Guardrails | Empty/whitespace, over 1,500 characters, secrets, and 13-digit IDs are rejected client- and server-side |
| Evidence | Sources remain visible and safe; no unsupported correctness/confidence claim appears |
| Encoding | Thai combining marks and emoji match fixtures in source, raw JSON, and browser rendering; no `U+FFFD` |
| Accessibility | Keyboard-only navigation, focus, live response updates, language, and reduced motion are verified |
| API behavior | Success, invalid payload, timeout, abort, rate limit, network error, and server error are distinct |

## Verification Commands

From `frontend/`:

```powershell
npm ci
npm run check
```

From `backend/` after its environment is prepared:

```powershell
python -c "import main"
python -m unittest discover -s tests -p "test_*.py"
```

From the repository root:

```powershell
git diff --check
git status --short --branch
```

Browser verification must cover desktop/mobile, drawer focus, new/select/delete while pending, stop/retry, real known-topic submission, no-source fallback, source expansion, long table overflow, Thai/English switching, and a clean console.

## Integration and Handoff

Merge work in this order: Agent A → Agent B → Agent C → Agent D → Agent E/tooling normalization. Resolve behavior against the invariants, not by taking one side of a textual conflict. Do not weaken sanitization or server validation to make tests pass.

The root orchestrator must produce `docs/validation/frontend-hardening-report.md` containing baseline/HEAD, file summary, dependency changes, test output, browser matrix, known limitations, and an explicit readiness statement. Completion requires all acceptance rows to pass, a clean `git diff --check`, and no unintended files changed. Stop before commit, push, or deployment unless separately authorized by the owner.
