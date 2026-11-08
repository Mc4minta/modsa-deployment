# Round 3 fixes report

- Branch: `modsa-vm`
- HEAD: `17fd82555d24bf323b5d14012eb243bec6696a1d`
- Date: `2026-11-08`
- No git commits, stages or pushes were made.

## Changes and unified diffs

```diff
diff --git a/backend/config.py b/backend/config.py
@@
     llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
+    llm_enable_thinking: bool | None = Field(default=None, alias="LLM_ENABLE_THINKING")
+    llm_max_tokens: int | None = Field(default=None, gt=0, alias="LLM_MAX_TOKENS")

diff --git a/backend/core/llm.py b/backend/core/llm.py
@@
-        _llm = ChatOpenAI(
+        kwargs = dict(
             model=settings.llm_model,
             api_key=settings.resolved_llm_api_key,
             base_url=settings.llm_base_url,
             temperature=0,
             timeout=settings.llm_timeout,
             max_retries=settings.llm_max_retries,
         )
+        if settings.llm_enable_thinking is not None:
+            kwargs["extra_body"] = {
+                "chat_template_kwargs": {
+                    "enable_thinking": settings.llm_enable_thinking,
+                },
+            }
+        if settings.llm_max_tokens is not None:
+            kwargs["model_kwargs"] = {"max_tokens": settings.llm_max_tokens}
+        _llm = ChatOpenAI(**kwargs)

diff --git a/backend/services/rag_service.py b/backend/services/rag_service.py
@@
+import logging
@@
+logger = logging.getLogger(__name__)
@@
+    answer = response.content
+    if not answer:
+        finish_reason = getattr(response, "response_metadata", {}).get("finish_reason")
+        logger.warning("LLM returned empty content; finish_reason=%s", finish_reason)
+        answer = no_verified_info_response(question)
@@
-        "answer": response.content,
+        "answer": answer,

diff --git a/backend/api/chat.py b/backend/api/chat.py
@@
+import logging
+import time
@@
+logger = logging.getLogger(__name__)
@@
+    started_at = time.perf_counter()
     try:
-        return answer_question(get_settings(), request.question)
+        result = answer_question(get_settings(), request.question)
     except Exception as exc:
-        raise HTTPException(status_code=500, detail=str(exc))
+        logger.exception("Chat request failed")
+        logger.info(
+            "Chat request outcome=error elapsed=%.3fs exception=%s",
+            time.perf_counter() - started_at,
+            type(exc).__name__,
+        )
+        raise HTTPException(
+            status_code=500,
+            detail="Internal server error",
+        ) from exc
+    logger.info(
+        "Chat request outcome=ok elapsed=%.3fs answer_length=%d source_count=%d",
+        time.perf_counter() - started_at,
+        len(result["answer"]),
+        len(result["sources"]),
+    )
+    return result

diff --git a/.env.vm.example b/.env.vm.example
@@
+# Reasoning models spend tokens on hidden reasoning. For this gateway, the
+# recommended model is qwen3.8-27b with thinking disabled for faster answers.
+LLM_ENABLE_THINKING="false"
+# Optional output cap; too small a value can truncate Thai answers.
+# LLM_MAX_TOKENS="800"

diff --git a/docs/DEPLOYMENT.md b/docs/DEPLOYMENT.md
@@
-`ngrok/ngrok:3.18.0`
+`ngrok/ngrok:latest`
@@
+## LLM timeouts and reasoning models
+
+Documents timeout/null-content symptoms, in-container model/chat timing
+diagnostics, the two optional settings, restart behavior, and live log fields.
+Unexpected backend failures are described as the generic
+`{"detail":"Internal server error"}` response.

diff --git a/backend/tests/test_llm.py b/backend/tests/test_llm.py
new file mode 100644
@@
+Tests default omission, enabled request parameters, and positive max-token
+validation using real no-network ChatOpenAI construction.

diff --git a/backend/tests/test_rag_service.py b/backend/tests/test_rag_service.py
new file mode 100644
@@
+Tests empty LLM content fallback and finish-reason warning logging.

diff --git a/backend/tests/test_chat_api.py b/backend/tests/test_chat_api.py
new file mode 100644
@@
+Tests generic 500 sanitization and exception-class request logging with a
+TestClient created without the lifespan context manager.
```

`docker-compose.yml` was not changed: the `ngrok` service already used
`ngrok/ngrok:latest`.

## ChatOpenAI parameter evidence

`backend/requirements.txt` declares `langchain-openai>=0.1`. The installed
package was inspected with `inspect.signature` on 2026-11-08 and reported
`langchain_openai 1.4.1`. Its `ChatOpenAI` signature explicitly includes
`extra_body` and `model_kwargs`, but not a direct `max_tokens` constructor
argument; it includes newer token fields instead. Constructing the actual
model with `model_kwargs={"max_tokens": 800}` produced `model_dump()["max_tokens"]
== 800`, while `extra_body` retained
`{"chat_template_kwargs": {"enable_thinking": False}}`. This is the compatible
way to preserve the gateway's `max_tokens` wire parameter without a network
call. The library emits a compatibility warning that the parameter was passed
through `model_kwargs`.

The frontend error client was read-only checked: `getErrorDetail` already uses
the JSON `detail` string and maps HTTP 500 to a server error, so the new generic
detail preserves the existing UI behavior. `frontend/src/services/api.ts` was
not modified.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Branch/upstream freshness | PASS | `git fetch`; `modsa-vm` equals `origin/modsa-vm` at `17fd825...` |
| Backend unittest discovery | PASS | `python -m unittest discover -s tests -p "test_*.py"`; 13 tests |
| Backend import | PASS | `python -c "import main"` from `backend/` |
| Chroma side effects | PASS | Existing `backend/chroma_db` remained; tests did not create or alter it |
| Frontend API error cross-check | PASS | `frontend/src/services/api.ts` and tests inspected |
| Frontend `npm run check` | PASS | lint warnings only; typecheck, 40 tests, and build passed |
| Compose YAML parse | PASS | PyYAML `safe_load` returned successfully |
| CR-character check | PASS | Every edited file is LF-only |
| Git status/stat | PASS | Read-only commands run; changes remain uncommitted |
| Live health/chat smoke test | NOT RUN | No VM/gateway session was started; would require deployment credentials |

## Deviations

- `docker-compose.yml` was intentionally left unchanged because it already
  used `ngrok/ngrok:latest`; the stale `3.18.0` reference in the deployment
  runbook was updated.
- `LLM_MAX_TOKENS` is forwarded through `model_kwargs` because the installed
  `ChatOpenAI` signature does not expose a direct constructor parameter, while
  the resulting request model state retains `max_tokens`.
- No frontend files were touched.

## Open questions

- Confirm on the VM that the gateway accepts the `max_tokens` and
  `chat_template_kwargs` fields exactly as expected after deployment.
- Revisit the Compose image tag and pin a verified immutable tag later.

## Exact VM `.env` values

Set these values after reviewing the gateway behavior:

```dotenv
LLM_MODEL="qwen3.8-27b"
LLM_ENABLE_THINKING="false"
LLM_MAX_TOKENS="800"
```

Adjust or remove `LLM_MAX_TOKENS` if Thai answers are truncated.

END OF REPORT
