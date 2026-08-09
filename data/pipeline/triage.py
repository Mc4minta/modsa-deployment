"""Triage: classify each source file by how it must be converted.

Run from the repo root:

    python -m data.pipeline.triage
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "raw"
SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


def classify(path: Path) -> dict[str, str]:
    ext = path.suffix.lower()
    if ext in {".txt", ".md"}:
        return {"type": "text", "action": "clean -> .md"}
    if ext == ".docx":
        return {"type": "docx", "action": "MarkItDown -> .md"}
    if ext == ".pdf":
        return {"type": "pdf", "action": "Typhoon OCR (+fallback text) -> .md"}
    return {"type": "unsupported", "action": "skip"}


def iter_sources(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED and path.name != ".gitkeep":
            yield path


def main() -> None:
    rows = [(str(p), *classify(p).values()) for p in iter_sources(INPUT_DIR)]
    if not rows:
        print(f"No source files found under {INPUT_DIR}/")
        return

    width = max(len(r[0]) for r in rows)
    print(f"{'FILE'.ljust(width)}  {'TYPE'.ljust(12)}  ACTION")
    print("-" * (width + 32))
    for file, typ, action in rows:
        print(f"{file.ljust(width)}  {typ.ljust(12)}  {action}")

    need_ocr = sum(1 for r in rows if r[1] == "pdf")
    print(f"\nTotal: {len(rows)} files | Typhoon OCR (PDF): {need_ocr} | docx/txt/md ไม่ OCR")


if __name__ == "__main__":
    main()
