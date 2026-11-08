#!/usr/bin/env bash
set -euo pipefail

# POST /admin/reindex is a synchronous def handler that deletes the Chroma
# collection before re-embedding. Because the blocking call runs in FastAPI's
# sync threadpool, chat and health can respond while it runs; verify at runtime.
# Retrieval is empty first, then partial, if indexing fails; the manifest is
# saved only on success.
# The key is expanded inside the container and is never a command-line argument.

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! RESPONSE="$(
    docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T backend \
        sh -c 'curl --fail-with-body --silent --show-error --max-time 900 \
          -X POST http://127.0.0.1:8000/admin/reindex \
          -H "X-Admin-Key: ${ADMIN_API_KEY}"'
)"; then
    echo "Reindex failed; inspect backend logs and /health." >&2
    exit 1
fi
printf '%s\n' "$RESPONSE"
