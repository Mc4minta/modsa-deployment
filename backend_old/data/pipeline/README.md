# Data Preparation Pipeline (ฝั่ง DATA)

แปลงเอกสารต้นฉบับ → **chunks JSON พร้อม metadata** ส่งให้ฝั่ง RAG ผ่านโฟลเดอร์ `chunks/`

```
data/raw/  ──normalize──►  data/processed/  ──chunk──►  chunks/   ──► (ฝั่ง RAG อ่าน)
 (ต้นฉบับ)                  (markdown สะอาด)            (handoff, structure-aware chunks)
```

| ชนิดไฟล์ | วิธีแปลง |
|---|---|
| `.pdf` | **Typhoon OCR** ทีละหน้า (ทุกไฟล์ ไม่แยกสแกน/มีข้อความอยู่แล้ว) + clean |
| `.docx` | MarkItDown (ข้อความ/ตาราง native ไม่ต้อง OCR) + clean |
| `.txt` / `.md` | clean อย่างเดียว |

> PDF ทุกไฟล์ผ่าน Typhoon OCR เหมือนกันหมดแล้ว (ไม่แยกแบบเดิมที่ดึงข้อความตรงด้วย PyMuPDF สำหรับไฟล์ที่มีข้อความอยู่แล้ว) เพื่อให้ตารางกับเลขหน้าออกมารูปแบบเดียวกันทุกไฟล์

## โฟลเดอร์ข้อมูล (ต้องสร้างเอง — ไม่ถูก commit)

`data/raw/`, `data/processed/`, `chunks/` ทั้ง 3 อยู่ใน `.gitignore` (กันไฟล์เอกสาร/JSON ขนาดใหญ่ขึ้น git) แปลว่า **clone repo มาใหม่จะไม่มี 3 โฟลเดอร์นี้เลย** ต้องสร้าง `data/raw/<หมวด>/` เองแล้วเอาไฟล์ต้นฉบับไปวาง (รับไฟล์จากเพื่อนในทีม/ไดรฟ์กลาง ไม่ใช่จาก git):

```
data/raw/registration/   data/raw/fees/            data/raw/academic_rules/
data/raw/scholarship/    data/raw/dormitory/       data/raw/academic_calendar/
data/raw/others/
```

## ติดตั้งครั้งแรก

```bash
brew install poppler                       # Typhoon OCR ต้องใช้ (macOS)
pip install -r data/requirements.txt
```

ใส่ API key ใน `.env` (ที่ root) — แทนค่า `your-typhoon-ocr-key`:

```env
TYPHOON_OCR_API_KEY="sk-..."
```

> ขอ key ได้ที่ https://opentyphoon.ai · rate limit 2 req/s, 20 req/min (ระบบหน่วง 3.5 วิ/หน้าให้อัตโนมัติ)

ทางเลือก: `pip install pythainlp` — ถ้ามีไว้ `chunk.py` จะใช้ตัดประโยคไทยตอนเจอข้อความยาวผิดปกติ (ไม่ติดตั้งก็ทำงานได้ปกติ ใช้ตัดที่ช่องว่างแทน)

## วิธีใช้ (รันจาก root ของโปรเจค)

```bash
# 1) คัดว่าไฟล์ไหนต้องทำอะไร (ไม่เรียก OCR ไม่ต้องมี key)
python -m data.pipeline.triage

# 2) ต้นฉบับ -> markdown สะอาด (เรียก Typhoon ทีละหน้า เฉพาะ .pdf)
python -m data.pipeline.normalize

# 3) markdown -> chunks JSON + metadata (อ่าน data/sources.json)
python -m data.pipeline.chunk
```

ผลลัพธ์: `data/raw/fees/x.pdf` → `data/processed/fees/x.md` → `chunks/fees/x.json`

### ขั้นตอน 2 — normalize: ควรรู้ก่อนรัน

- **ข้ามไฟล์ที่แปลงแล้วทั้งไฟล์**: ถ้า `data/processed/fees/x.md` มีอยู่แล้วจะข้ามทั้งไฟล์ (กันจ่าย Typhoon API ซ้ำ) — อยากแปลงใหม่ ให้ลบ `.md` ตัวนั้นก่อน
- **OCR ล้มเหลวรายหน้า ไม่ retry**: หน้าไหน error (เช่น timeout กับตารางซับซ้อน) จะถูกข้ามทันทีและ mark `<!-- page: N (OCR FAILED) -->` ไว้ ส่วนหน้าอื่นที่ผ่านยังถูกเขียนออกมาปกติ
- **หน้าที่ FAILED จะหายเงียบๆ ถ้าไม่ไปแก้**: หน้านั้นจะไม่มีเนื้อหาใน chunk เลย (ไม่มี error ให้เห็นตอน chunk) ต้องเช็กเองด้วย:
  ```bash
  grep -rl "OCR FAILED" data/processed/
  ```
  แล้วเปิด `.md` ไฟล์นั้น หาเนื้อหาหน้าที่ค้างมาใส่แทนบรรทัด `<!-- page: N (OCR FAILED) -->` (คง `<!-- page: N -->` ไว้ให้ `chunk.py` อ่านเลขหน้าถูก)
- ไฟล์ที่ error **ทั้งไฟล์** (เช่น ลืมใส่ API key) จะไม่เขียน `.md` ออกมาเลย → รันซ้ำจะพยายามแปลงใหม่ให้อัตโนมัติ (ต่างจาก error รายหน้าด้านบนที่ไฟล์ถูกเขียนออกมาแล้วเลยจะถูกข้ามในรอบถัดไป)

### ขั้นตอน 3 — chunk: ตัดแบบ structure-aware

ไม่ได้ตัดทุกๆ ~1000 ตัวอักษรตรงๆ แต่ดูโครงสร้างเอกสารก่อนตัด ให้แต่ละ chunk เป็นหน่วยที่ตอบคำถามได้ครบในตัวเอง:

| ชนิดเนื้อหา | ตัวอย่างไฟล์ | ตัดยังไง |
|---|---|---|
| ตาราง | ค่าเทอม, ปฏิทิน | ตัดเป็นกลุ่มแถว ~1000 ตัวอักษร โดย **หัวตาราง + บริบทหน้าตาราง** (เช่น ชื่อคณะ/วันที่) ติดซ้ำไปทุก chunk |
| ระเบียบ/ข้อบังคับ | rule_exam2560, discipline2566 | **1 ข้อ/มาตรา = 1 หน่วย ไม่ตัดกลางข้อ** แม้ข้อนั้นจะคร่อมหน้า; ข้อที่ยาวเกินไปตัดที่ข้อย่อย (21.1, 21.2, …) แทน |
| คู่มือ/ขั้นตอน | คู่มือลงทะเบียน, ถอน New ACIS | รวม Step/ย่อหน้าในหัวข้อเดียวกัน ไม่ตัดข้ามหัวข้อ (`#`/`##`) |
| ร้อยแก้ว/FAQ | ประกาศทุน, ติดต่อทะเบียน | รวมย่อหน้าในหัวข้อเดียวกันจนเต็ม chunk |

ทุก chunk มี **breadcrumb บอกที่มา** เป็นบรรทัดแรกเสมอ ช่วยตอบคำถามกว้างๆ/ข้ามหมวดได้ดีขึ้น เพราะตัว chunk ไม่ได้ลอยๆ ไม่รู้ที่มาอีกต่อไป:

```
[ค่าเทอม/ค่าใช้จ่าย | 20Mar69-ค่าใช้จ่ายตลอดหลักสูตรปตรี-69 | คณะวิศวกรรมศาสตร์]
| สาขาวิชา | ปริญญา | ... |
| วิศวกรรมคอมพิวเตอร์ | วศ.บ. | ... | เหมาจ่าย 30,000/ภาคการศึกษา | ... |
```

Block ที่ใหญ่ผิดปกติ (เกิน 1,600 ตัวอักษร และไม่มีจุดตัดตามโครงสร้างให้ใช้) จะ fallback ไปตัดตามบรรทัดแล้วช่องว่าง — ภาษาไทยไม่มีเว้นวรรคระหว่างคำ แต่มีเว้นวรรคระหว่างวลี จึงยังไม่ตัดกลางคำ (ถ้าลง `pythainlp` ไว้จะเปลี่ยนไปตัดที่ประโยคแทน)

**Schema JSON ไม่เปลี่ยนจากเดิม** ฝั่ง RAG (`modsa_rag/ingest.py`) ใช้ต่อได้เลยไม่ต้องแก้อะไร:
```json
{ "doc_id": "...", "metadata": {...}, "chunks": [ { "chunk_id", "content", "page", "section" } ] }
```

ปรับขนาด chunk ได้ที่หัวไฟล์ `data/pipeline/chunk.py` (`CHUNK_SIZE` / `CHUNK_MIN` / `CHUNK_MAX`) — ค่านี้แยกจาก `CHUNK_SIZE`/`CHUNK_OVERLAP` ใน `.env` ฝั่ง RAG (อันนั้นใช้เฉพาะตอนโหลดไฟล์ดิบตรงๆ โดยไม่ผ่าน pipeline นี้)

## เติม metadata ให้ citation สวย

ทุกครั้งที่รัน `chunk`, ไฟล์ใหม่ใน `data/processed/` ที่ยังไม่มี entry จะถูก **auto-generate template ใส่ `data/sources.json` ให้เอง** (title เดายังไงก็ได้จากชื่อไฟล์ department/source_url/contact ว่างไว้) พร้อม print รายชื่อไฟล์ที่เพิ่งเพิ่มให้เห็นท้ายรัน — ไม่ต้องสร้าง entry เองมือ แค่ไปแก้ **`data/sources.json`** เติม title ให้อ่านง่าย + department/source_url/contact ต่อไฟล์ แล้วรัน `python -m data.pipeline.chunk` ใหม่อีกรอบ
— อย่าแก้ใน `chunks/*.json` เพราะถูก generate ทับทุกครั้ง

ถ้าไฟล์ใน `data/processed/` ถูกลบ/เปลี่ยนชื่อ entry เก่าใน `sources.json` จะไม่ถูกลบอัตโนมัติ (กันข้อมูลที่กรอกไว้หาย) แต่ `chunk` จะเตือน `⚠️ data/sources.json มี N entry ที่ไม่มีไฟล์ processed แล้ว` ท้ายรัน — เช็กแล้วค่อยลบ/ย้าย entry นั้นไปไว้ที่ doc_id ใหม่เอง

## หลังรันเสร็จ

1. เช็กหน้า OCR ที่ยังไม่ผ่าน: `grep -rl "OCR FAILED" data/processed/` แล้วไปแก้ให้ครบก่อน chunk รอบสุดท้าย
2. 🔴 **ตรวจของเสี่ยง** (เงิน/วันที่/เกณฑ์ทุน) ใน `data/processed/` กับต้นฉบับ — OCR/extract อาจผิดเงียบๆ
3. ⚠️ **วรรณยุกต์ที่หาย** (เช่น `คาใชจาย` → `ค่าใช้จ่าย`) `clean` ซ่อมไม่ได้ ต้องแก้มือใน `data/processed/`
4. ฝั่ง RAG อ่าน `chunks/` อยู่แล้ว (`.env`: `RAG_SOURCE_PATHS="chunks"`) → รีสตาร์ทแอปเพื่อ re-index (หรือยิง `POST /reindex`)

## หมายเหตุ

- จุดส่งต่อระหว่าง 2 ฝั่งคือ **`chunks/` เท่านั้น** (ฝั่ง RAG ไม่ยุ่งกับ `data/`)
- `data/raw/`, `data/processed/`, `chunks/` **ไม่ถูก commit** — แชร์ไฟล์ต้นฉบับกับเพื่อนนอก git แล้วให้แต่ละคนรัน pipeline เอง ผลลัพธ์ (`data/processed/`, `chunks/`) จะไม่ตรงกันเป๊ะถ้าคนละเวอร์ชัน OCR — ถ้าจะแชร์ผลลัพธ์กันจริง ส่งทั้งโฟลเดอร์ `chunks/` ตรงๆ ไปเลยจะชัวร์กว่า
- ไฟล์ที่ error ทั้งไฟล์ (เช่น ยังไม่ใส่ API key) จะถูกข้ามและรายงานท้ายรัน ไฟล์อื่นยังแปลงต่อ
