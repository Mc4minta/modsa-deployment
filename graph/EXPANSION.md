# Phase12 — สร้างกราฟจาก chunks ชุดใหม่

โหมดนี้ไม่ใช้รายการ27chunksหรือคำถาม50ข้อของpilot. ใช้ชนิดnode/เส้นเชื่อมจากschemaเดิม และเพิ่มmetadata profile `+source-metadata-v1` อัตโนมัติ รับJSONเอกสารหนึ่งไฟล์หรือdirectoryใต้ `data/chunks/` โดยแต่ละไฟล์คือเอกสารทั้งฉบับหนึ่งรุ่น

Profileนี้เก็บ `source_uri`, `topic_tags`, `content_type`, `effective_until`, `ingested_at`, `supersedes` ลงกราฟด้วย โดยไม่แก้schema/ผลตรวจpilotเดิม. `supersedes` เป็นรายการIDรุ่นที่ต้นทางระบุ ไม่ใช่การสั่งลบ/ปิดรุ่นเก่า. ไม่มีการเดาวันหรือสถานะที่ขาด. Schema hash/cache key ของexpansionเปลี่ยนจากก่อนเพิ่มprofile จึงไม่แอบนำcacheคนละschemaมาใช้และไม่เรียกAPIทดแทนอัตโนมัติ

ติดตั้งตาม [QUICKSTART](QUICKSTART.md) ก่อน ใช้เฉพาะrequirementsกราฟได้ ไม่ต้องเริ่มbackend/Chroma. `build/load` แบบpilotเดิมยังอยู่และไม่ถูกแทนที่

## 1. วางแผนโดยไม่ส่งข้อมูล

```sh
python graph/run.py expand --input data/chunks/fees --check
```

แสดงจำนวนเอกสาร/chunks/คำขอสกัดที่ยังขาด ไม่อ่านAPIkey ไม่สร้างไฟล์ ไม่เชื่อมDB. เลือกไฟล์เดียวแทนdirectoryได้ เลือกเอกสารทั้งฉบับเสมอ ไม่ตัดแค่บางchunksให้identityของรุ่นเดียวกันเปลี่ยนตามbatch

รูปแบบJSONใช้schemaเดิมของทีมData: `doc_id`, `metadata`, `chunks[{chunk_id,content,page}]`. ต้องมีdoc_id/chunk_idไม่ซ้ำและcontentไม่ว่าง; ไม่รับsymlinkออกนอก `data/chunks/`. ไม่ทำOCRหรือแบ่งchunksใหม่

## 2. สกัดเมื่ออนุญาตข้อมูลและค่าใช้จ่ายแล้ว

ตั้ง `MIMO_API_KEY` ใน `.env` หรือenvironment. ตัวสกัดใช้ `mimo-v2.6-pro` ไม่ใช่โมเดลGemma4ของตัวตอบ

```sh
python graph/run.py expand --input data/chunks/fees --extract --max-calls 126
```

126เป็นเพียงตัวอย่างจากจำนวนchunksในหมวดfeesปัจจุบัน ให้ใช้จำนวนmissingจาก `--check` ของชุดที่เลือกจริง ห้ามเพิ่มงบทั้งคลังโดยไม่ตรวจ scope. ถ้างบไม่พอจะหยุดก่อนส่งAPIทั้งหมด. ไม่มีautomatic retry/model repair/provider fallback;หนึ่งattemptต่อchunkที่ขาด หากล้มเหลวจะหยุดและเก็บcacheที่สำเร็จไว้ รันซ้ำด้วยงบที่อนุญาตจึงจะลองงานที่failedอีกครั้ง

ส่งเฉพาะPRIMARYกับchunkแรก/เพื่อนบ้านใกล้เคียงของเอกสารรุ่นเดียวกันเพื่อscope ไม่ส่งเฉลยหรือข้อมูลจากคำถามpilot. ทุกข้อเท็จจริงต้องมีquoteจากPRIMARYและผ่านตัวตรวจschema/ตัวเลข/ข้อยกเว้นเดิม. แต่quoteตรงไม่ได้รับรองความสัมพันธ์เชิงความหมายหรือสิทธิ์ตามนโยบาย

## 3. สร้างซ้ำจากcache / ตรวจผล

```sh
python graph/run.py expand --input data/chunks/fees --build
```

คำสั่งนี้ไม่เรียกAPI. ผลอยู่ `graph/expansions/batches/<batch_id>/graph.json` และREADMEสรุปแต่ละเอกสาร. JSONรวม source/version, source quotes, unresolved notes และrun_idที่ต้องใช้ตรวจ. โฟลเดอร์expansionsทั้งหมดไม่เข้าGit รวมcacheและผลLLM; เพื่อนต้องสกัดของตนเองหรือรับผลที่ได้รับอนุญาตแยกต่างหาก

เอกสารเดิมที่inputs/model/prompt/schemaเหมือนเดิมใช้cacheซ้ำ. เพิ่มเอกสารใหม่ในbatchไม่เปลี่ยนrunของเอกสารเดิม. เปลี่ยนเนื้อหาเอกสารหนึ่งฉบับสร้างversionใหม่และสกัดใหม่เฉพาะฉบับนั้น (ทุกchunkของรุ่นนั้น) ไม่สกัดทั้งคลังใหม่

## 4. เพิ่มเข้า Neo4j แบบ opt-in

เปิดNeo4jตาม [QUICKSTART](QUICKSTART.md) และตรวจผลก่อน:

```sh
python graph/run.py expand --input data/chunks/fees --load
```

ไม่เรียกLLM. ต้องมีexportที่ตรงกับsource/schema/cacheปัจจุบันทุกส่วน มิฉะนั้นปฏิเสธการโหลด. Importเอกสารทั้งbatchในtransactionเดียว ตรวจreadbackและimportซ้ำในtransactionนั้น หากมีข้อผิดพลาดrollbackทั้งbatch (อาจมีการสร้างconstraintเทคนิคไว้ก่อนแล้ว). ตรวจfingerprintข้อมูลนอกbatchก่อน–หลังรวม2รอบ ไม่สแกนซ้ำทุกเอกสาร และตรวจเนื้อหาของทุกrunอีกครั้งก่อนcommit. บันทึกผลที่load.json

ใช้namespaceต่อเอกสารรุ่น/กราฟ/schema ไม่ใช่รวมข้อมูลทุกbatchเป็นrunเดียว. โหลดซ้ำrunเดิมเพิ่ม0/0;เพิ่มbatchใหม่ไม่ลบpilotหรือrunอื่น. เป็นstagingใช้labelเทคนิคMODSAPilotร่วมกับloaderเดิม โดยrunขึ้นต้น `modsa-expansion-v1:`. ทุกnodeยังPENDING/retrieval_enabled=false ไม่อนุมัติACTIVE/VERIFIEDและไม่เปิดHybridในAPI

เมื่อโหลดแล้วสามารถส่งสำเนาให้เพื่อนโดยไม่ต้องส่งcacheหรือสกัดซ้ำ: ดูคำสั่ง `transfer export --batch ...` ใน [TRANSFER.md](TRANSFER.md)

ค้นในNeo4j Browserโดยใช้run_idจากexport:

```cypher
MATCH (a:MODSAPilot {run_id: $run_id})-[r]->(b:MODSAPilot)
RETURN a,r,b LIMIT 100;
```

## ขอบเขตที่ยังไม่ใช่ความสามารถของโหมดนี้

- ใช้ชนิดnode/เส้นเชื่อมเดิมพร้อมmetadata profile ไม่ค้นพบschemaใหม่อัตโนมัติ ประเภทentityยังจำกัดตามoutput contractเดิม
- ตัวสกัดเลือกได้สูงสุด3factsต่อPRIMARY/6entities/2offerings จึงไม่ใช่การรับรองว่าดึงทุกfactในเอกสารครบ
- Contextยังเป็นchunkแรกกับเพื่อนบ้าน ไม่ใช่section-aware parserหรือการแก้ตารางOCR
- ไม่มีcross-document entity merge/global alias resolution; entityยังผูกscope/versionเพื่อไม่รวมชื่อผิด
- รุ่นเก่าอยู่ร่วมกับรุ่นใหม่ ไม่ทำsupersede/delete/ตัดสินนโยบายปัจจุบันอัตโนมัติ
- Local evidence validationไม่ใช่semantic approval; ต้องประเมินข้อมูลใหม่และคำถามใหม่ก่อนเปิดใช้งานจริง
- รันทีละprocess ไม่รองรับparallel writers/การรับรองquotaระหว่างหลายเครื่อง

การมีโหมดขยายไม่ได้แปลว่าpilotถูกอนุมัติผ่านหรือPhase12 productionเสร็จทั้งหมด แต่เป็นเครื่องมือให้ทดลองขยายข้อมูลได้โดยไม่ผูกpilot IDs/QAแล้ว

## ผลตรวจ implementation

ทดสอบ input/LLM จำลองที่มีหลายเอกสารและจำนวนchunksต่างจากpilot, cache reuse, เปลี่ยนรุ่นเอกสาร, budgetก่อนส่งAPI, quotesปลอม, cacheผิดidentity และ buildที่ล้มเหลวไม่ทับexportเดิม. ทดสอบNeo4jจริงในcontainerชั่วคราวแยกport17688ด้วยข้อมูลจำลอง: แรก10nodes/10edges → ซ้ำ0/0 → ฉีดfailureหลังเขียนเอกสารใหม่แล้วrollbackเหลือ10nodesเดิม → โหลดเอกสารใหม่สำเร็จเพิ่ม5/5. ไม่แตะฐานpilotเดิม ไม่เรียกCloud

ยังไม่ได้ทดสอบสกัดข้อมูลใหม่จริงด้วยMiMo/วัดsemantic qualityหรือcoverageของทั้งคลัง. `--check` ของคลังปัจจุบันพบ71เอกสาร/1233chunks/1233คำขอที่ยังขาด จึงต้องเลือกscopeและอนุญาตงบก่อนรัน ไม่ได้เริ่มคำขอเหล่านี้อัตโนมัติ

รอบแก้reviewเพิ่มtestsสำหรับcomparatorsที่ผูกกับตัวเลขเป้าหมาย (ไม่ใช้คำขั้นต่ำ/ไม่เกินจากทั้งก้อน), metadata export และการตรวจนอกbatch2รอบแม้มี71เอกสาร. Testsเหล่านี้ไม่เรียกCloudและไม่เขียนNeo4jจริง
