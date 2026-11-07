#!/usr/bin/env bash
# ==============================================================================
# scripts/reindex.sh - Trigger MOD-SA Vector Database Reindexing
# ==============================================================================
# Executes POST /admin/reindex securely from INSIDE the backend container.
# The reindex endpoint is not reachable through Nginx or Cloudflare Tunnel.
#
# WARNING: Reindexing drops the existing ChromaDB collection and re-embeds all
# 253 chunk documents from scratch using the configured external embedding API.
# This will consume external API tokens and may take several minutes.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

# 1. Load ADMIN_API_KEY from environment or .env file
if [[ -z "${ADMIN_API_KEY:-}" ]]; then
    if [[ -f .env ]]; then
        ADMIN_API_KEY=$(grep -E '^[[:space:]]*ADMIN_API_KEY=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d '\r' || true)
    fi
fi

if [[ -z "${ADMIN_API_KEY:-}" || "${ADMIN_API_KEY}" == "generate-a-strong-random-secret-here" || "${ADMIN_API_KEY}" == "change-me" ]]; then
    echo "ERROR: Valid ADMIN_API_KEY is not set in environment or .env file." >&2
    echo "Please set ADMIN_API_KEY in .env before executing reindex." >&2
    exit 1
fi

# 2. Check if the backend container is running
if ! docker compose ps --services --filter "status=running" | grep -q "^backend$"; then
    echo "ERROR: Backend container is not running. Start the stack first:" >&2
    echo "  docker compose up -d backend" >&2
    exit 1
fi

echo "======================================================================"
echo "Starting vector store reindexing inside backend container..."
echo "Target: http://localhost:8000/admin/reindex"
echo "Note: Admin API key is passed securely via container exec (not echoed)."
echo "======================================================================"

# Execute curl inside container without printing key to logs
RESPONSE=$(docker compose exec -T backend sh -c 'curl -sS -f -X POST http://localhost:8000/admin/reindex -H "X-Admin-Key: '"${ADMIN_API_KEY}"'"' 2>&1)
EXIT_CODE=$?

if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo ""
    echo "Reindexing completed successfully!"
    echo "Response: ${RESPONSE}"
else
    echo ""
    echo "ERROR: Reindexing failed with exit code ${EXIT_CODE}." >&2
    echo "Output: ${RESPONSE}" >&2
    exit ${EXIT_CODE}
fi
