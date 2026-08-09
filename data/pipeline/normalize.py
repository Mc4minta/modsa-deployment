"""Normalize every source file into clean Markdown under data/processed/.

    PDF         -> Typhoon OCR (hosted API) ทีละหน้า -> markdown-only + clean
                   (หน้าไหน OCR error -> ข้ามทันที + mark '(OCR FAILED)' ไว้ทำมือทีหลัง)
    .docx       -> MarkItDown -> markdown + clean
    .txt / .md  -> clean

ต้องมี TYPHOON_OCR_API_KEY ใน .env (+ `brew install poppler` บน macOS)
Output mirrors the input folders: data/raw/fees/x.pdf -> data/processed/fees/x.md

ไฟล์ที่มี output ใน data/processed/ แล้วจะถูก "ข้าม" (กัน OCR ซ้ำ/จ่าย API ซ้ำ)
— ถ้าอยาก OCR ใหม่ ให้ลบไฟล์ .md ตัวนั้นออกก่อน

Run from the repo root:

    python -m data.pipeline.normalize
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import fitz  # PyMuPDF (นับจำนวนหน้า)
from dotenv import load_dotenv

from pipeline.clean import clean_thai_text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

INPUT_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"
SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
OCR_DELAY_SEC = 3.5  # stay under Typhoon's 20 req/min limit


# ── Typhoon HTML output -> markdown-only ──────────────────────────────
def _clean_cell(html: str) -> str:
    html = re.sub(r"<br\s*/?>", " ", html)
    html = re.sub(r"<[^>]+>", "", html)  # strip tags ที่เหลือ (b, th ฯลฯ)
    return html.replace("|", "/").strip()


def _table_to_markdown(table_html: str) -> str:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    parsed, ncol = [], 0
    for row in rows:
        cells = [_clean_cell(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)]
        if cells:
            parsed.append(cells)
            ncol = max(ncol, len(cells))
    if not parsed:
        return ""
    out = []
    for i, cells in enumerate(parsed):
        cells = cells + [""] * (ncol - len(cells))
        out.append("| " + " | ".join(cells) + " |")
        if i == 0:
            out.append("| " + " | ".join(["---"] * ncol) + " |")
    return "\n".join(out)


def to_markdown_only(text: str) -> str:
    """แปลง <table>/<figure>/<page_number> ที่ Typhoon คายมา ให้เป็น markdown ล้วน"""
    text = re.sub(r"<table[^>]*>.*?</table>",
                  lambda m: _table_to_markdown(m.group(0)), text, flags=re.DOTALL)
    text = re.sub(r"<figure>(.*?)</figure>", lambda m: m.group(1).strip(), text, flags=re.DOTALL)
    text = re.sub(r"<page_number>[^<]*</page_number>", "", text)  # เรามี <!-- page --> เอง
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ── conversion ────────────────────────────────────────────────────────
def ocr_pdf_typhoon(path: Path) -> str:
    api_key = os.getenv("TYPHOON_OCR_API_KEY")
    if not api_key or api_key.startswith("your-"):
        raise RuntimeError("TYPHOON_OCR_API_KEY is not set in .env — required for OCR")
    from typhoon_ocr import ocr_document  # lazy import

    doc = fitz.open(path)
    pages = len(doc)
    doc.close()

    parts: list[str] = []
    for page_num in range(1, pages + 1):
        try:
            page_md = ocr_document(
                pdf_or_image_path=str(path),
                page_num=page_num,
                task_type="v1.5",
                api_key=api_key,  # hosted API (base_url ดีฟอลต์)
            )
            print(f"    OCR page {page_num}/{pages} ...", flush=True)
            parts.append(f"<!-- page: {page_num} -->\n{to_markdown_only(page_md)}")
        except Exception as exc:  # error ครั้งเดียว -> ข้ามหน้านั้นทันที (mark ไว้ทำมือทีหลัง)
            print(f"    page {page_num}: FAILED ({exc}) -> ข้าม", flush=True)
            parts.append(f"<!-- page: {page_num} (OCR FAILED) -->")
        if page_num < pages:
            time.sleep(OCR_DELAY_SEC)
    return clean_thai_text("\n\n".join(parts))


def convert_markitdown(path: Path) -> str:
    from markitdown import MarkItDown  # lazy import (.docx: native text/tables, ไม่ต้อง OCR)

    return MarkItDown().convert(str(path)).text_content


def convert(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".txt", ".md"}:
        return clean_thai_text(path.read_text(encoding="utf-8", errors="replace"))
    if ext == ".docx":
        return clean_thai_text(convert_markitdown(path))
    if ext == ".pdf":
        return ocr_pdf_typhoon(path)  # OCR ทุกหน้า; หน้าไหน OCR ไม่ได้ -> fallback text (ในตัว)
    raise ValueError(f"unsupported file type: {path}")


def main() -> None:
    sources = [
        p
        for p in sorted(INPUT_DIR.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED and p.name != ".gitkeep"
    ]
    if not sources:
        print(f"No source files found under {INPUT_DIR}/")
        return

    ok = skipped = 0
    for path in sources:
        out_path = OUTPUT_DIR / path.relative_to(INPUT_DIR).with_suffix(".md")
        if out_path.exists():
            print(f"• มีแล้ว ข้าม: {out_path.relative_to(ROOT)}")
            skipped += 1
            continue
        print(f"• {path.name}  ->  {out_path.relative_to(ROOT)}")
        try:
            md = convert(path)
        except Exception as exc:  # keep going; report at the end
            print(f"    skip: {exc}")
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        ok += 1

    print(f"\nDone: แปลงใหม่ {ok} ไฟล์, ข้าม(มีแล้ว) {skipped} ไฟล์ -> {OUTPUT_DIR}/")
    print("เตือน: ตรวจของเสี่ยง 🔴 (เงิน/วันที่/ทุน) กับต้นฉบับก่อนนำไปใช้")


if __name__ == "__main__":
    main()
