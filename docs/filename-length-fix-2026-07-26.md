# Filename length fix — 2026-07-26

## Problem

Render.com deploy failed on `git clone` checkout:

```
error: unable to create file backend_old/data/processed/academic_rules/ระเบียบ...(ฉบับที่ 2).md: File name too long
```

Root cause: filesystem (ext4, used by Render's build image) limits filename to **255 bytes**, not 255 characters. Thai text is 3 bytes/char in UTF-8, so long Thai filenames blow past the limit fast. Windows/NTFS (dev machine) allows it, which is why it worked locally and only broke on deploy.

## Files that exceeded 255 bytes (renamed)

| Old name (truncated) | New name |
|---|---|
| `ระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี-ว่าด้วย-การศึกษาระดับบัณฑิตศึกษา-(ฉบับที่ 2).md/json` (256/258 bytes) | `grad-study-regulation-no2.md/json` |
| `ขั้นตอนการพิมพ์ใบเสร็จรับเงินค่าลงทะเบียนเรียน-(แบบออนไลน์)-ระบบสารสนเทศเพื่อการบริหารการศึกษา-(New ACIS).md/json` (288/290 bytes) | `tuition-receipt-print-steps-acis.md/json` |

Renamed in all 5 locations each file existed: `backend_old/data/raw`, `backend_old/data/processed`, `datasets/raw`, `datasets/processed`, `datasets/chunks` (json only for chunks).

Content untouched — `title`, `source_name` fields inside the chunk JSON still carry the full original Thai name. Only the filename on disk changed. Nothing in code (`pipeline/`, `services/`, config) referenced these filenames directly, so no other changes needed.

## How to check for this in future

Byte length, not character count, is what matters:

```bash
python3 -c "
import os
for root, dirs, files in os.walk('datasets'):
    for f in files:
        b = len(f.encode('utf-8'))
        if b > 200:
            print(b, os.path.join(root, f))
"
```

Rule of thumb for this dataset: **Thai filename should stay under ~80 Thai characters** (80 × 3 bytes ≈ 240 bytes, leaves headroom for extension). Everything else in the current dataset is under 174 bytes — safe margin, no other renames needed right now.

## Recommendation for adding new files

- Keep filenames short ASCII slugs (like the two renamed above) or short Thai titles.
- Put the full descriptive title in the `title` / `source_name` metadata field instead of the filename — that's already the pattern used elsewhere in this repo.
- If unsure, run the byte-length check above before committing new dataset files.
