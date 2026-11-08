# Round 2 VM + ngrok + Vercel fixes report

## Header

- Branch: `modsa-vm`.
- HEAD: `772448fd39068c3eedb51c161471caf7499a5b7b`.
- Date: 2026-11-08.
- Required files were present: `docs/DEPLOYMENT.md` and `nginx/nginx.conf`.
- No git commits, stages or pushes were made.

## Fix 1 — Nginx catch-all and security headers

```diff
diff -- nginx/nginx.conf
@@
+        location / {
+            return 404;
+        }
@@
         location @json_404 {
             add_header Access-Control-Allow-Origin "*" always;
+            add_header X-Content-Type-Options nosniff always;
         }
```

The same `X-Content-Type-Options` header was added to all named 413, 429, 502,
503, and 504 error locations. The explicit catch-all ensures `/` and unknown
paths use the server's JSON 404 error page.

## Fix 2 — CORS tests without lifespan ingestion

```diff
diff -- backend/tests/test_cors.py
@@
-        with TestClient(app) as client:
-            response = client.options(...)
+        client = TestClient(app)
+        response = client.options(...)
```

Both tests now avoid the context manager, so application lifespan startup does
not run real ingestion. The targeted backend suite passed 8 tests. A directory
check reported `chroma_db` entries unchanged from 2 before to 2 after.

## Fix 3 — Backup retention

```diff
diff -- scripts/backup.sh
@@
-    printf '%s\n' "${old_archives[@]:KEEP:}" | xargs -r rm -f --
+    printf '%s\n' "${old_archives[@]:KEEP}" | xargs -r rm -f --
```

The retention slice now uses the valid omitted-length form. A throwaway Bash
test with 10 dummy archives and `KEEP=7` reported
`retention_before=10 retention_after=7`. The existing newline-based deletion
pipeline was retained; unusual filenames are not expected because generated
archive names contain only timestamp characters.

## Fix 4 — Backend memory limit

```diff
diff -- docker-compose.yml
@@
-    mem_limit: 2g
+    # First-boot indexing and heavy imports need headroom; the VM has 16 GB.
+    mem_limit: 4g
```

No other Compose setting was changed for this fix.

## Fix 5 — README Docker guidance

```diff
diff -- README.md
@@
-From repo root (requires `.env`):
-...
-docker compose up --build
+For the VM/ngrok stack, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and
+copy [.env.vm.example](.env.vm.example) to `.env`.
```

The old Docker instructions were replaced with the VM runbook pointer and VM
environment example. `data/chunks` exists, while `datasets/chunks` does not;
the stale `datasets/chunks` references outside the Docker section were left
untouched because the requested README scope was the Docker section only.

## Fix 6 — VM environment comments

```diff
diff -- .env.vm.example
@@
-# Assigned from the ngrok dashboard Domains page.
+# Assigned from the ngrok dashboard Domains page. Use the bare domain only:
+# no https:// and no path; Compose adds https:// for the tunnel command.
 NGROK_DOMAIN="<assigned-static-dev-domain>"
+
+# Reindexing re-embeds all chunks with the current EMBEDDING_* values. Use the
+# tolerant FIRST BOOT values above before reindexing, then restore STEADY STATE.
```

Only comments were changed.

## Fix 7 — Deployment runbook and reindex semantics

The runbook now documents the 600-second backend health start period,
`docker compose logs -f backend` in a second terminal, and the retry procedure
after an unhealthy first boot. It documents that `/admin/reindex` is a
synchronous `def` handler, so FastAPI runs the blocking call in its sync
threadpool and health/chat can respond; this is explicitly marked
“unverified at runtime.” It also requires tolerant embedding values before
reindex, `docker compose up -d`, then steady-state values and another
`docker compose up -d`.

The tunnel section includes the `X-Forwarded-For: 1.2.3.4` spoof test, log
interpretation, and stop/report action. The Vercel rollout is now Preview first,
then Production. Troubleshooting includes ngrok tag/domain failures, HEAD
method behavior, and the VM Nginx validation command. The backend test command
is documented from `backend/`.

The reindex header comment was updated accordingly:

```diff
diff -- scripts/reindex.sh
@@
-# and health remain reachable during the operation, but retrieval is empty
-# first, then partial, if indexing fails; the manifest is saved only on success.
+# collection before re-embedding. Because the blocking call runs in FastAPI's
+# sync threadpool, chat and health can respond while it runs; verify at runtime.
+# Retrieval is empty first, then partial, if indexing fails; the manifest is
+# saved only on success.
```

Representative runbook diff:

```diff
diff -- docs/DEPLOYMENT.md
@@
-[ ] Set ... for Production and Preview.
+[ ] Set ... for Preview only; deploy and test the stable branch alias first.
+[ ] Only after preview succeeds, set the same variables for Production.
@@
+[ ] From `backend/`, run `python -m unittest discover -s tests -p "test_*.py"`.
```

## Verification

| Check | Result | Evidence |
|---|---|---|
| Branch and required files | PASS | `modsa-vm`; both required files exist |
| Backend tests | PASS | `python -m unittest discover -s tests -p "test_*.py"`; 8 tests |
| Chroma side-effect check | PASS | Entries 2 before and 2 after; no test-created change |
| Frontend checks | NOT RUN | Frontend was not touched in this round |
| Bash syntax | PASS | `bash -n scripts/backup.sh scripts/restore.sh scripts/reindex.sh` |
| Backup retention | PASS | 10 dummy archives reduced to 7 |
| Compose YAML | PASS | PyYAML parsed both Compose files |
| CR-character check | PASS | CR count 0 in every edited file |
| Runbook cross-check | PASS | Services, scripts, env vars, paths, and endpoints referenced by edits exist |
| Docker Compose config | NOT RUN | Docker unavailable |
| Nginx syntax | NOT RUN | Nginx/Docker unavailable |
| ShellCheck | NOT RUN | ShellCheck unavailable |
| Git status/diff | PASS | Read-only checks completed; no staging/commit/push |

## Deviations or unfinished items

- Nginx runtime behavior, Compose health ordering, and the real-IP spoof test
  remain unverified because Docker/Nginx are unavailable in this environment.
- The retention test used a temporary LF Bash script because Windows PowerShell
  line translation corrupted direct piped Bash input; the temporary file was
  removed.
- Existing stale `datasets/chunks` references outside the README Docker section
  were not changed due to the explicit narrow README scope.

## Open questions

1. What exact VM, Vercel, and ngrok domains should replace the placeholders?
2. Are the selected image tags and ngrok agent command syntax approved and
   available on Docker Hub?
3. Does the VM's Nginx access log confirm ngrok preserves the real public IP?
4. Should the stale non-Docker README references be corrected in a later,
   separately scoped documentation change?

END OF REPORT
