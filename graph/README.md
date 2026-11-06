# Graph build

โค้ดสร้าง/ตรวจ/โหลดกราฟจาก `data/chunks/`. ไม่มีโค้ด eval หรือรายงานทดลองในชุดนี้; `/chat/ask` ยังเป็น Vector เดิม.

## ติดตั้ง

ใช้ Python 3.12 จาก root ของ repository:

```sh
python3 -m venv .venv-graph
source .venv-graph/bin/activate
python -m pip install -r graph/build/requirements.txt
```

Windows ใช้ `py -3.12 -m venv .venv-graph` และ `.\.venv-graph\Scripts\python.exe` แทน `python` โดยไม่ต้อง activate.

## เอกสารใหม่ → กราฟ

```sh
python graph/run.py expand --input data/chunks/<file-or-folder> --check
# หลังอนุมัติข้อมูล/งบแล้วเท่านั้น:
python graph/run.py expand --input data/chunks/<file-or-folder> --extract --max-calls <approved-calls>
python graph/run.py expand --input data/chunks/<file-or-folder> --build
```

`--check` ไม่เขียนไฟล์/เรียก API; `--extract` ใช้ OpenRouter และ `OPENROUTER_API_KEY` จาก `.env`; `--build` ใช้ cache โดยไม่เรียก API. ผล/cache/สถิติ JSON อยู่ `graph/expansions/` และไม่เข้า Git. หากตั้งใจ reuse ผล MiMo เดิม ให้ใส่ `--reuse-mimo-cache` เหมือนกันทุกคำสั่ง. อย่าลบ reservation ของงาน UNKNOWN เพื่อฝืนส่งซ้ำ; ไม่รองรับ parallel writers.

## Neo4j และสำเนากราฟ

```sh
python graph/run.py init-neo4j
docker compose --env-file .graph-pilot.env -f graph/compose.yaml up -d --wait --wait-timeout 150
python graph/run.py expand --input data/chunks/<file-or-folder> --load
```

`--load` เขียน Neo4j staging หลัง build ตรงกับข้อมูลปัจจุบัน และสร้าง `load_verification.json`. ใช้เฉพาะ loopback port 17687; ถ้ามีฐานเดิมให้ใช้ credentials เดิม ไม่ลบ volume/เปลี่ยนรหัสเอง.

```sh
python graph/run.py transfer export --batch <batch>/graph.json --out <new-copy>.json
python graph/run.py transfer check --file <copy>.json
python graph/run.py transfer load --file <copy>.json
python graph/run.py transfer verify --batch <batch>/graph.json --out <new-report>.json
```

Export/verify อ่านฐานอย่างเดียว; transfer load เขียนฐานของผู้รับ. สำเนามี schema/chunk text/quotes ไม่ต้องมี extraction cache หรือ API key เพื่อโหลด. ส่งเฉพาะผู้ได้รับอนุญาต และห้ามส่ง `.env`/`.graph-pilot.env`. ไม่เปิด Hybrid หรืออนุมัตินโยบายให้อัตโนมัติ.

## ไฟล์ที่จำเป็นและการทดสอบ

- `build/`, `run.py`, `compose.yaml`, `requirements.txt`: สกัด/validate/export/โหลดฐาน.
- `data/inputs/schema.json`: config JSON เพียงไฟล์เดียวในชุดโค้ด กำหนด node/relationship/property types และตรวจ fingerprint.
- `data/chunks/*.json` ที่ root ของโปรเจกต์: ข้อมูลต้นทาง ไม่ใช่ไฟล์ทดลองของกราฟ.
- `tests/`: ป้องกันข้อมูลหาย, ส่ง API ซ้ำ, เปลี่ยนตัวเลข/quotes และโหลดข้าม namespace.
- README นี้เก็บไว้ไฟล์เดียวเพื่อแยกคำสั่งอ่านข้อมูล/API/เขียนฐานให้รันได้ปลอดภัย.

คำสั่งย่อใช้เส้นทาง expand สำหรับข้อมูลปัจจุบัน ไม่ replay pilot เดิม:

```sh
python graph/run.py check
python graph/run.py build --input data/chunks/<file-or-folder>
PYTHONPATH=backend python3 -m unittest discover -s graph/tests
```

`check` วางแผนจาก `data/chunks/` โดยไม่อ่าน pilot/คำถาม/ผลทดลองเดิม. `build` ต้องมี extraction cache ที่ตรงกับ input จึงจะสร้าง graph ได้; clone โค้ดอย่างเดียวไม่มีผลสกัดทั้งคลัง ต้องอนุมัติ `expand --extract` พร้อมงบ หรือรับสำเนากราฟผ่าน transfer. ห้ามแก้เป็นเรียก LLM อัตโนมัติเมื่อ cache ขาด.

Tests ใช้ข้อมูลจำลองใน Python ไม่ใช้ JSON ของ pilot; tests ที่ใช้ runtime ต้องติดตั้ง `backend/requirements.txt` เพิ่ม. ไม่มีการเรียก API หรือเปิดฐานจากคำสั่ง check/build. สร้างรายงาน contract JSON แยกได้ด้วย `python graph/build/contracts.py` (ผลอยู่ `graph/expansions/contracts.json`, ไม่เข้า Git); `--check` ตรวจโดยไม่เขียนผล.

ชื่อภายในเดิม เช่น `MODSAPilot`, `pilot_id` และ `.graph-pilot.env` คงไว้เพื่อไม่เปลี่ยน namespace/cache identity ของกราฟที่สร้างแล้ว ไม่ได้อ่านไฟล์ pilot เดิม.

ทุก node ยัง PENDING/retrieval ปิด. Quote ตรงไม่รับรอง semantic quality/coverage; ยังมีข้อจำกัด 3 facts ต่อ chunk, entity identity ตาม scope และ unit validation ที่ต้องพัฒนาต่อก่อน production. ไม่มี reranker/การเปิด Hybrid จากชุดสร้างกราฟนี้. Usage ที่ขาดคือ UNKNOWN ไม่ใช่ศูนย์; ดู `stats.json`/`requests.jsonl` สำหรับต้นทุนและ failures.
