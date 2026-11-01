from __future__ import annotations

import hashlib
from pathlib import Path


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
