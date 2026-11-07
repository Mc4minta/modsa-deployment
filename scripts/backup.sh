#!/usr/bin/env bash
# ==============================================================================
# scripts/backup.sh - Backup Persistent ChromaDB Vector Store
# ==============================================================================
# Safely archives ./data/chroma into ./backups/ with a timestamp.
# The backend container is briefly stopped to prevent SQLite corruption during
# tar archive creation.
#
# IMPORTANT NOTES:
# 1. The .env file contains sensitive API secrets and is NOT included here.
#    Back up .env separately and store it in a secure password manager or vault.
# 2. The entire index can always be rebuilt from source data in data/chunks/
#    using scripts/reindex.sh. This backup saves embedding API time and costs.
# 3. Always copy backups OFF the VM to remote secure storage.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

BACKUP_DIR="${ROOT_DIR}/backups"
CHROMA_DIR="${ROOT_DIR}/data/chroma"
KEEP_BACKUPS="${KEEP_BACKUPS:-5}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="${BACKUP_DIR}/chroma_backup_${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

if [[ ! -d "${CHROMA_DIR}" ]]; then
    echo "ERROR: Chroma directory ${CHROMA_DIR} does not exist. Nothing to backup." >&2
    exit 1
fi

echo "======================================================================"
echo "MOD-SA ChromaDB Backup"
echo "Timestamp:    ${TIMESTAMP}"
echo "Source:       ${CHROMA_DIR}"
echo "Destination:  ${ARCHIVE_NAME}"
echo "Retention:    Keep latest ${KEEP_BACKUPS} archives"
echo "======================================================================"

# Check if backend container is running
BACKEND_WAS_RUNNING=0
if docker compose ps --services --filter "status=running" 2>/dev/null | grep -q "^backend$"; then
    BACKEND_WAS_RUNNING=1
    echo "Stopping backend container briefly to ensure SQLite database integrity..."
    docker compose stop backend
fi

cleanup() {
    if [[ ${BACKEND_WAS_RUNNING} -eq 1 ]]; then
        echo "Restarting backend container..."
        docker compose start backend || true
    fi
}
trap cleanup EXIT

echo "Creating compressed tar archive..."
tar -czf "${ARCHIVE_NAME}" -C "${ROOT_DIR}/data" chroma

ARCHIVE_SIZE=$(du -h "${ARCHIVE_NAME}" | cut -f1)
echo "Backup created successfully: ${ARCHIVE_NAME} (${ARCHIVE_SIZE})"

# Prune older archives exceeding retention limit
echo "Pruning older backup archives (retention = ${KEEP_BACKUPS})..."
OLD_COUNT=0
while IFS= read -r old_archive; do
    if [[ -n "${old_archive}" && -f "${old_archive}" ]]; then
        echo "Removing obsolete archive: ${old_archive}"
        rm -f "${old_archive}"
        OLD_COUNT=$((OLD_COUNT + 1))
    fi
done < <(ls -1dt "${BACKUP_DIR}"/chroma_backup_*.tar.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)))

echo "Pruned ${OLD_COUNT} old backup(s)."

echo "======================================================================"
echo "REMINDER: Copy ${ARCHIVE_NAME} OFF THIS VM to secure remote storage."
echo "Backup saved in: ${ARCHIVE_NAME}"
echo "======================================================================"
