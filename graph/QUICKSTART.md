# เริ่มบนเครื่องใหม่

ถ้าได้รับ**สำเนากราฟที่สร้างเสร็จแล้ว** ให้ใช้ [TRANSFER.md](TRANSFER.md) แทนขั้นbuild/replayด้านล่าง ผู้รับไม่ต้องมีsource chunksหรือLLM cache

ต้องมี Python3.12 (รุ่นที่ทดสอบ) และ source repository ที่มี `graph/` กับ `data/chunks/` ครบ. ไม่ต้องมี `.local/`, cache, backend, Ollama หรือ API key สำหรับขั้น1–2. คำสั่งต่อไปนี้รันจาก root ของ repository

## 1. ติดตั้งครั้งเดียว

macOS/Linux:

```sh
python3 -m venv .venv-graph
source .venv-graph/bin/activate
python -m pip install -r graph/build/requirements.txt
```

Windows PowerShell (ไม่ต้อง activate หรือเปลี่ยน execution policy):

```powershell
py -3.12 -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r graph/build/requirements.txt
```

Windows ให้ใช้ `.\.venv-graph\Scripts\python.exe` แทน `python` ในคำสั่งด้านล่าง

## 2. สร้าง export โดยไม่เสีย API

```sh
python graph/run.py check
python graph/run.py build
```

ผลที่ต้องได้: 24primary chunks, 40candidate facts, 134nodes/231edges. กราฟอยู่ `graph/data/results/graph.json`. ตัวbuildตรวจและสร้างใหม่จากผลสกัดที่เก็บไว้ ไม่ได้เรียก LLM ใหม่ ไม่เขียน Neo4j หรือเปลี่ยนข้อมูลต้นทาง

Buildทำในdirectoryชั่วคราวก่อนเผยแพร่ผลทั้งหมด จึงไม่เขียนทับbundle/exportเดิมเมื่อvalidationล้มเหลว. เอกสารที่เพิ่มนอกpilotไม่เปลี่ยนsnapshotเดิม; inventoryของbundleเป็นfrozen baseline ส่วนcontractsแสดงจำนวนทั้งคลังปัจจุบัน

นี่คือ pilot27chunks/9เอกสาร ไม่ใช่สร้างกราฟทั้ง1233chunks และไม่ใช่เปิดระบบตอบคำถาม. `build` ทำซ้ำได้จาก source repository โดยไม่อาศัยผลทดลองที่Git ignore

## 3. โหลดกราฟลง Neo4j ของเครื่องนี้

ต้องติดตั้งและเปิด Docker พร้อม Compose v2 ก่อน ใช้ฐานเฉพาะgraph แยกจาก Composeของbackend

```sh
python graph/run.py init-neo4j
docker compose --env-file .graph-pilot.env -f graph/compose.yaml up -d --wait --wait-timeout 150
python graph/run.py load
python graph/run.py inspect
```

`init-neo4j` สุ่มรหัสผ่านและเก็บใน `.graph-pilot.env` โดยไม่พิมพ์รหัสผ่าน ไม่ทับไฟล์เดิม และGit ignoreไว้. บนmacOS/Linuxจำกัดสิทธิ์ไฟล์0600; บนWindowsควรจำกัดสิทธิ์เข้าถึงไฟล์ด้วยบัญชีของตนเอง

ผล load ต้องเป็น `VERIFIED:134nodes/231edges; second load created0/0`. Loaderตรวจnode/edge/propertyครบและทดสอบรุ่นจำลองแล้วrollback ไม่ลบกราฟเดิม ไม่เปิดretrieval

เปิด Neo4j Browser ที่ http://127.0.0.1:17474 ใช้ connection `bolt://127.0.0.1:17687`, user `neo4j`; รหัสผ่านอยู่หลัง `neo4j/` ในค่า `NEO4J_AUTH` ของไฟล์เฉพาะเครื่อง อย่าส่งไฟล์นี้ให้เพื่อนหรือcommit

ดูกราฟใน Browser:

```cypher
MATCH (a:MODSAPilot)-[r]->(b:MODSAPilot)
RETURN a, r, b LIMIT 80;
```

## หยุด / แก้ปัญหา

- Port17474/17687ถูกใช้: ถ้ามีฐานpilotเดิมอยู่แล้ว อย่าเริ่มComposeซ้อนหรือหยุดฐานเดิมโดยไม่ตรวจสอบ ใช้ credentialsเดิมกับ `load/inspect` หรือทดสอบบนเครื่องใหม่ ชุดนี้ตั้งใจจำกัดloopbackและport17687 ไม่ใช่ตัวติดตั้งฐานremote
- ถ้าฐานเพิ่งเริ่มและloadแจ้งเชื่อมไม่ได้: รอให้เริ่มเสร็จแล้วสั่งloadซ้ำ (ไม่เรียกLLM). Healthcheckตรวจprocess จึงอาจเร็วกว่าBoltพร้อมใช้งานเล็กน้อย
- ถ้ารหัสผ่านไม่ตรงหลังเคยสร้างvolume: อย่าลบ/สร้าง `.graph-pilot.env` ใหม่; NEO4J_AUTHตั้งรหัสผ่านตอนฐานว่างเท่านั้น ไม่ใช่คำสั่งเปลี่ยนรหัสผ่านvolumeเดิม
- หยุดโดยเก็บข้อมูล: `docker compose --env-file .graph-pilot.env -f graph/compose.yaml down`. อย่าเติม `-v` เพราะจะลบข้อมูลในvolume
- Missing module: ใช้Pythonจาก`.venv-graph`และติดตั้งrequirementsด้านบน ไม่ใช้Python globalโดยไม่ตั้งใจ
- Source/snapshot/review mismatch: หยุดตรวจไฟล์ที่เปลี่ยน ไม่ข้ามvalidationหรือยืนยันข้อมูลใหม่อัตโนมัติ

## การสกัดข้อมูลใหม่ (แยกจากquick start)

สำหรับเอกสารที่ไม่ใช่pilot ให้ใช้ [โหมดexpand](EXPANSION.md) แทนคำสั่งpilotด้านล่าง; ไม่ต้องสร้างคำถาม50ข้อหรือแก้รายการpilot

ตัวสกัดpilotใช้ MiMo Pro และ `MIMO_API_KEY` จาก `.env` หรือenvironment. คำสั่ง `python graph/build/extract.py --pilot --extract` ขอเฉพาะงานที่ขาด อาจมีค่าใช้จ่ายและส่งข้อความเอกสารออกไป ต้องอนุญาตก่อน ไม่ใช่ขั้นตอนจำเป็นเพื่อให้เพื่อนสร้างexportเดิม

หลังแก้pilot/schema/source ต้องทวนsnapshotและหลักฐาน ไม่ใช่แค่รันคำสั่งเดิมแล้วถือว่าข้อมูลใหม่ผ่าน. ยังไม่มี workflowขยายทั้งคลังหรือupdate/deleteครบ

## ขอบเขตที่ตรวจแล้ว

ทดสอบบนmacOS/Python3.12 ด้วยvirtualenvใหม่ติดตั้งเฉพาะ7แพ็กเกจที่pinในrequirements และสำเนาเฉพาะ `graph/` + `data/chunks/` (ไม่มีbackend/archive/APIkey/cache) ผ่านcheck/build. ตรวจComposeconfigด้วยcredentialsใหม่ และทดสอบโหลดNeo4jฐานว่างแยกport17688ผ่านloaderfunctionsสองรอบ (134/231→0/0); ไม่ทดสอบComposeขึ้นที่portมาตรฐานในเครื่องนี้เพราะฐานเดิมใช้อยู่. Windows/Linuxมีคำสั่งให้แต่ยังไม่ได้ทดสอบบนเครื่องจริง

ไฟล์ชุดนี้ต้องถูกcommit/pushหรือส่งsourceให้ครบก่อนเครื่องอื่นใช้งาน ยังไม่ได้มีการcommit/pushโดยอัตโนมัติ
