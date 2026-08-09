from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config import Settings


MANIFEST_FILE = "source_manifest.json"


def file_fingerprint(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
    }


def build_manifest(files: list[Path]) -> dict[str, object]:
    return {"files": [file_fingerprint(path) for path in files]}


def manifest_path(settings: Settings) -> Path:
    return settings.chroma_dir / MANIFEST_FILE


def load_manifest(settings: Settings) -> dict[str, object] | None:
    path = manifest_path(settings)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(settings: Settings, manifest: dict[str, object]) -> None:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(settings).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
