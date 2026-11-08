#!/usr/bin/env bash
set -euo pipefail

# Restores an archive containing top-level chroma/. The old directory is moved
# aside, never recursively deleted. The backend is restarted only if it ran.

if [[ ${EUID} -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
fi
if [[ $# -ne 1 ]]; then
    echo "Usage: sudo bash scripts/restore.sh backups/chroma-<timestamp>.tar.gz" >&2
    exit 2
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/chroma"
ARCHIVE="$(realpath -- "$1")"
TMP_DIR="$(mktemp -d)"
WAS_RUNNING=0

cleanup() {
    rm -rf -- "$TMP_DIR"
    if [[ $WAS_RUNNING -eq 1 ]]; then
        docker compose -f "$ROOT_DIR/docker-compose.yml" up -d backend >/dev/null || true
    fi
}
trap cleanup EXIT

[[ -f "$ARCHIVE" ]] || { echo "Archive not found: $ARCHIVE" >&2; exit 1; }
tar -tzf "$ARCHIVE" | grep -Eq '^chroma(/|$)' || {
    echo "Archive must contain top-level chroma/" >&2
    exit 1
}
if [[ -n "$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q --status running backend)" ]]; then
    WAS_RUNNING=1
fi
docker compose -f "$ROOT_DIR/docker-compose.yml" stop backend >/dev/null
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
mkdir -p "$ROOT_DIR/data"
if [[ -d "$DATA_DIR" ]]; then
    mv -- "$DATA_DIR" "$ROOT_DIR/data/chroma.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
mv -- "$TMP_DIR/chroma" "$DATA_DIR"
chown -R 10001:10001 "$DATA_DIR"
chmod 750 "$DATA_DIR"
echo "Restored $ARCHIVE; previous data was moved aside."
