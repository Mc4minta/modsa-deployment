# data_pipeline

Data prep pipeline: raw source docs → clean Markdown → structure-aware JSON chunks for the RAG backend.

Code lives here (`data_pipeline/`); data lives in `../datasets/` (`raw/`, `processed/`, `chunks/`).

```
datasets/raw/  ──normalize──►  datasets/processed/  ──chunk──►  datasets/chunks/   ──► (ฝั่ง RAG อ่าน)
```

## Layout

| Path | Contains |
|---|---|
| `pipeline/triage.py` | Dry-run classification of raw files (no OCR calls) |
| `pipeline/check_filenames.py` | Flags raw filenames over the 255-byte filesystem limit |
| `pipeline/normalize.py` | Raw docs → clean Markdown (Typhoon OCR for PDF, MarkItDown for docx) |
| `pipeline/clean.py` | Shared Thai-text cleanup helper |
| `pipeline/chunk.py` | Processed Markdown → JSON chunks + metadata |
| `sources.json` | Human-edited metadata sidecar (title, department, source_url, contact per doc) |
| `requirements.txt` | Pipeline-only Python deps |

## Run (from repo root)

```bash
pip install -r data_pipeline/requirements.txt

python -m data_pipeline.pipeline.triage           # dry-run, no OCR
python -m data_pipeline.pipeline.check_filenames  # flag raw filenames too long for filesystem
python -m data_pipeline.pipeline.normalize        # raw -> processed (needs TYPHOON_OCR_API_KEY in root .env)
python -m data_pipeline.pipeline.chunk       # processed -> chunks JSON
```

Full docs, gotchas, and the `sources.json` metadata workflow: [`pipeline/README.md`](pipeline/README.md).
