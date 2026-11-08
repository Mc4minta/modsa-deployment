#!/usr/bin/env bash
set -euo pipefail

# The backend is stopped briefly. Chroma is a bind mount owned by 10001:10001.
# The archive contains top-level chroma/ and is verified before retention cleanup.

if [[ ${EUID} -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/chroma"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
KEEP="${KEEP:-7}"
WAS_RUNNING=0
ORIGINAL_USER="${SUDO_USER:-$(id -un)}"
ORIGINAL_GROUP="$(id -gn "$ORIGINAL_USER")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="$BACKUP_DIR/chroma-$STAMP.tar.gz"

restart_backend() {
    if [[ $WAS_RUNNING -eq 1 ]]; then
        docker compose -f "$ROOT_DIR/docker-compose.yml" up -d backend >/dev/null
    fi
}
trap restart_backend EXIT

mkdir -p "$BACKUP_DIR"
if [[ -z "$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q --status running backend)" ]]; then
    WAS_RUNNING=0
else
    WAS_RUNNING=1
fi
docker compose -f "$ROOT_DIR/docker-compose.yml" stop backend >/dev/null
tar -czf "$ARCHIVE" -C "$DATA_DIR/.." chroma
tar -tzf "$ARCHIVE" >/dev/null
chown "$ORIGINAL_USER:$ORIGINAL_GROUP" "$ARCHIVE"

mapfile -t old_archives < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'chroma-*.tar.gz' -printf '%T@ %p\n' | sort -rn | awk '{print $2}')
if (( ${#old_archives[@]} > KEEP )); then
    printf '%s\n' "${old_archives[@]:KEEP}" | xargs -r rm -f --
fi
echo "Created $ARCHIVE"
