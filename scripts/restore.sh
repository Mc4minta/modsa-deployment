#!/usr/bin/env bash
# ==============================================================================
# scripts/restore.sh - Restore ChromaDB Vector Store from Backup Archive
# ==============================================================================
# Usage:
#   scripts/restore.sh <path-to-archive.tar.gz> [--yes]
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <path-to-backup-archive.tar.gz> [--yes]" >&2
    echo "Available backups in ./backups/:" >&2
    ls -lh "${ROOT_DIR}/backups"/chroma_backup_*.tar.gz 2>/dev/null || echo "  (no backups found)" >&2
    exit 1
fi

ARCHIVE_PATH="$1"
CONFIRM_FLAG="${2:-}"

if [[ ! -f "${ARCHIVE_PATH}" ]]; then
    echo "ERROR: Backup archive not found: ${ARCHIVE_PATH}" >&2
    exit 1
fi

CHROMA_DIR="${ROOT_DIR}/data/chroma"

echo "======================================================================"
echo "MOD-SA ChromaDB Restore"
echo "Source archive: ${ARCHIVE_PATH}"
echo "Target path:    ${CHROMA_DIR}"
echo "======================================================================"

if [[ "${CONFIRM_FLAG}" != "--yes" && "${CONFIRM_FLAG}" != "-y" && "${FORCE:-0}" != "1" ]]; then
    echo "WARNING: This operation will overwrite all existing data in ${CHROMA_DIR}!"
    read -r -p "Are you sure you want to proceed with restore? [y/N]: " CONFIRMATION
    if [[ "${CONFIRMATION}" != "y" && "${CONFIRMATION}" != "Y" && "${CONFIRMATION}" != "yes" ]]; then
        echo "Restore cancelled by user."
        exit 0
    fi
fi

# Stop backend container before restoring files
BACKEND_WAS_RUNNING=0
if docker compose ps --services --filter "status=running" 2>/dev/null | grep -q "^backend$"; then
    BACKEND_WAS_RUNNING=1
    echo "Stopping backend container..."
    docker compose stop backend
fi

cleanup() {
    if [[ ${BACKEND_WAS_RUNNING} -eq 1 ]]; then
        echo "Restarting backend container..."
        docker compose start backend || true
    fi
}
trap cleanup EXIT

echo "Preparing target data directory..."
mkdir -p "${ROOT_DIR}/data"
rm -rf "${CHROMA_DIR}"

echo "Extracting archive..."
tar -xzf "${ARCHIVE_PATH}" -C "${ROOT_DIR}/data"

# Ensure permissions match backend container appuser (UID 10001, GID 10001)
if command -v chown >/dev/null 2>&1; then
    if [[ $(id -u) -eq 0 ]]; then
        chown -R 10001:10001 "${CHROMA_DIR}"
    else
        echo "Note: If backend fails with permission errors, run:"
        echo "  sudo chown -R 10001:10001 ${CHROMA_DIR}"
    fi
fi

echo "ChromaDB restored successfully from ${ARCHIVE_PATH}."
