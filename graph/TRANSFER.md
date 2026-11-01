# ส่งสำเนากราฟให้เพื่อน — ไม่สกัดด้วย LLM ใหม่

ส่งไฟล์ `graph/transfers/modsa-pilot-copy.json` พร้อม **source code โฟลเดอร์ graph/ รุ่นที่มีคำสั่ง transfer**. ไม่ส่ง `.env`, `.graph-pilot.env`, API key, cache หรือ Chroma disk. ถ้าเพื่อนมีโปรเจกต์อยู่แล้ว ต้องอัปเดตโค้ดคำสั่งนี้ก่อน (ไฟล์ที่ยังไม่commit/pushจะไม่ตามไปกับclone)

ชุดที่เตรียมส่งครั้งนี้: `graph/transfers/modsa-graph-copy.zip` รวมเครื่องมือนำเข้า, requirements, คู่มือและJSONสำเนาไว้แล้ว เพื่อนแตกZIPในโฟลเดอร์ใหม่แล้วรันจากโฟลเดอร์ที่มี `graph/` ได้ ไม่ต้องcloneโปรเจกต์ทั้งชุดหรือรอcommit. ZIPนี้เป็นสำเนาตามเวลาที่สร้าง ไม่อัปเดตเองเมื่อโค้ด/กราฟเปลี่ยน

สำเนาปัจจุบันคือpilot **134 nodes / 231 relationships** ไม่ใช่ทั้งคลัง1233chunks. ส่งออกหลังอ่านตรวจเทียบrunในNeo4jจริงแล้ว ไม่มีการแก้ฐานต้นทาง. นี่เป็นlogical copyเฉพาะmanaged run ที่เลือก ไม่ใช่backupทุกอย่างในNeo4j ไม่รวมผู้ใช้/รหัสผ่าน/ฐานอื่น/กราฟที่สร้างด้วยมือ

## เพื่อนทำอะไรบ้าง

รันจากrootโปรเจกต์ ติดตั้งPython3.12 + requirementsกราฟตาม [QUICKSTART ขั้น1](QUICKSTART.md). ใช้เฉพาะ `graph/` กับไฟล์สำเนาได้ ไม่ต้องมี `data/chunks/`, backend, pilot review, LLM cache หรือAPI key

1. ตรวจไฟล์แบบofflineก่อน ไม่อ่านcredentialsหรือเชื่อมฐาน:

   ```sh
   python graph/run.py transfer check --file graph/transfers/modsa-pilot-copy.json
   ```

2. เปิดNeo4jของเครื่องตนเอง ถ้ายังไม่มี ให้ติดตั้ง/เปิดDockerแล้วรัน:

   ```sh
   python graph/run.py init-neo4j
   docker compose --env-file .graph-pilot.env -f graph/compose.yaml up -d --wait --wait-timeout 150
   ```

   รหัสผ่านถูกสร้างใหม่เฉพาะเครื่อง ไม่ต้องใช้รหัสของผู้ส่ง. ถ้าเครื่องนี้มีNeo4jชุดเดิมที่port17687 ให้ใช้credentialsเดิม อย่าสร้างvolumeซ้อนหรือลบvolumeเพื่อแก้รหัสผ่าน

3. โหลดสำเนา:

   ```sh
   python graph/run.py transfer load --file graph/transfers/modsa-pilot-copy.json
   ```

   ฐานว่างควรเพิ่ม134nodes/231edges. รันซ้ำควรเพิ่ม0/0. Run IDs, node/edge IDs, properties, quotes และวันที่คงเดิม; nullยังเป็นpropertyที่ไม่มีค่าในNeo4j. แต่ละrunแยกnamespace ไม่มีการลบหรือรวมข้ามrun. หากrunIDเดิมมีเนื้อหาต่าง จะหยุด ไม่เขียนทับ

   Importทั้งหมดอยู่ในtransactionเดียว ตรวจreadback/รันซ้ำและกราฟนอกชุดก่อนcommit; ผิดพลาดrollback (constraintทางเทคนิคอาจสร้างไว้ก่อนแล้ว). คำสั่งไม่เรียกLLM ไม่เปลี่ยนChroma และไม่เปิดHybridในAPI

เปิด [Neo4j Browser](http://127.0.0.1:17474) แล้วใช้:

```cypher
MATCH (a:MODSAPilot)-[r]->(b:MODSAPilot)
RETURN a,r,b LIMIT 100;
```

Windowsใช้ `.\.venv-graph\Scripts\python.exe` แทน `python`. ตรวจสอบแบบofflineได้โดยยังไม่เปิดDocker

## ผู้ส่งสร้างสำเนาใหม่เมื่อกราฟเปลี่ยน

Pilotที่โหลดลงNeo4jแล้ว:

```sh
python graph/run.py transfer export --pilot --out graph/transfers/modsa-pilot-v2.json
```

Expansion batchที่โหลดลงNeo4jแล้ว:

```sh
python graph/run.py transfer export --batch graph/expansions/batches/<batch_id>/graph.json --out graph/transfers/modsa-expansion.json
```

ต้องใช้schemaที่ตรงกับexport และrunในฐานต้องตรงกับgraph exportทุกnode/edge/property. ถ้าขาดrun/แก้กราฟด้วยมือ/ข้อมูลไม่ตรง จะไม่สร้างไฟล์. คำสั่งexportอ่านNeo4jอย่างเดียว ไม่เรียกLLM. เลือกชื่อไฟล์ใหม่เสมอ ไม่ทับสำเนาเดิม. โฟลเดอร์transfersถูกGit ignoreเพื่อไม่เผยแพร่เนื้อหาเอกสารโดยไม่ตั้งใจ

ไฟล์JSONมีschema, graphและchecksum SHA-256 ในตัว. ผู้รับตรวจด้วยschemaที่แนบมา ไม่ต้องอาศัยschema/source/cacheบนเครื่องผู้ส่ง. ไม่มีการรันCypherจากไฟล์; importerสร้างคำสั่งจากชนิดที่ตรวจแล้วและส่งข้อมูลเป็นparameters

## ข้อควรทราบ

- สำเนามีข้อความchunkและหลักฐานquoteจริง แม้ไม่มีcredentialsก็อาจเป็นข้อมูลภายใน ส่งเฉพาะผู้ได้รับอนุญาต
- Checksumช่วยตรวจไฟล์เสีย/เปลี่ยน ไม่ใช่ลายเซ็นยืนยันผู้ส่งหรือรับรองความถูกต้องของนโยบาย ควรยืนยันchecksumกับผู้ส่งผ่านช่องทางที่เชื่อถือได้
- ทุกnodeยังPENDING/retrieval disabled. สำเนานี้ไม่ใช่การอนุมัติข้อมูล และ `/chat/ask` ยังVectorจนกว่าจะเชื่อมHybridโดยตั้งใจ
- ไม่รวมVector index/embeddings/ผลประเมิน/aliasesหรือประวัติreviewภายนอกกราฟ. ใช้คำสั่งนี้สำหรับกราฟMODSAในสถานะstaging ไม่ใช่กราฟACTIVEหรือbackupฐานทั่วไป
- ยังจำกัดNeo4jแบบloopback `bolt://127.0.0.1:17687`. รันทีละprocess; Windows/Linuxมีคำสั่งให้แต่ยังไม่ได้ทดสอบบนเครื่องจริง

## ผลทดสอบการส่งต่อ

ตรวจJSONด้วยvirtualenvที่มีเฉพาะrequirementsกราฟ ผ่าน. ทดสอบสำเนาเฉพาะcode+JSONโดยไม่มี `data/chunks/`, `graph/data/` หรือcache: offline checkผ่าน และโหลดNeo4jจริงในcontainerชั่วคราวแยกportได้134nodes/231edges → โหลดซ้ำ0/0. จำลองfailureหลังเขียนrunใหม่แล้วยืนยันrollbackเหลือ134/231เดิม. ลบcontainerทดสอบแล้ว ไม่เขียนNeo4jต้นทางและไม่เรียกLLM
