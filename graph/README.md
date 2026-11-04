# Graph build

**ข้อมูลใหม่ใช้ [EXPANSION](EXPANSION.md)**: `python graph/run.py expand --input data/chunks/<file-or-folder> --check` แล้วแยกอนุญาตการสกัด/โหลดจริง. ไม่ใช้pilot IDsหรือคำถามเดิม ไม่เปลี่ยนAPIหรืออนุมัติคุณภาพข้อมูลให้อัตโนมัติ

ตัวสกัด `expand` ใช้OpenRouter Muse Spark 1.3 Contributor กับ `OPENROUTER_API_KEY`; frozen pilotยังMiMoเดิม. ถ้าจะใช้ผลMiMoที่ผ่านแล้วร่วมด้วยให้ระบุ `--reuse-mimo-cache` ตามคู่มือ (mixed-model build ตรวจหลักฐานซ้ำและเก็บที่มาทุกรายการ)

อัปเดต4พ.ย.2026: ตัวตรวจ `source-layout-v4` ทวน cache ทั้งคลังโดยไม่สกัดซ้ำ; bounded repair ใช้ contract `typed-scope-v2` และเก็บผลก่อนซ่อม/สถิติแยก. Initial request ที่ขาดผลมี reservation กันส่งซ้ำ รวมกรณีตรวจพบbillingแล้วแต่ไม่มีcompleted output. ดู [ผลล่าสุดและข้อจำกัด](EXPANSION.md#ล่าสุดหลังรอบซ่อม-source-layout-v4). จำนวนที่ผ่าน local validation ไม่ใช่ semantic approval และยังไม่เปิด Hybrid/โหลด Neo4j อัตโนมัติ

ปิดงานค้างแล้ว: cache1233chunksไม่มีmissing/failedหลังsource curationและเติมผล1callในงบเดิม. มีAI source review28chunksที่ยังPENDING โดย17chunksเก็บข้อกำหนดเป็นsource textแทนnumeric interpretationที่ไม่ชัด และ15chunksไม่มีfacts. `--check`แสดงสถานะเหล่านี้แยก; ดู[สถานะปัจจุบันและการย้ายเครื่อง](EXPANSION.md#สถานะล่าสุด-cache-ครบ-1233-chunks-แต่ยังเป็น-pending). ไม่ใช่คะแนนโมเดล100%หรืออนุมัติproduction

Full exportสร้างและโหลดNeo4j stagingแล้ว: 71เอกสาร/1233chunks →7911nodes/17004edges; โหลดซ้ำเพิ่ม0/0 และpilotเดิมไม่เปลี่ยน. Build/loadใช้0LLM calls. อยู่ใต้`graph/expansions/batches/<batch_id>/` พร้อม`graph.json`,`EXPORT_REVIEW.md`,`NEO4J_STAGING.md`และรายงานJSON; ดูbatchปัจจุบันใน[EXPANSION](EXPANSION.md). ทุกnodeของbatchยังPENDING/retrievalปิด ไม่เปิดHybridในAPI. ผลเหล่านี้ไม่เข้าGit

ทดสอบ [offline retrieval replay](evaluation/README.md) บนdev34ข้อแล้ว: Vector4 recall64.15%, Graph4+4 recall71.84%, Vector8 recall81.26%. Graphยังไม่เพิ่มgold recallเหนือadjacency-only จึงยังไม่เปิดHybridหรืออ้างว่าดีกว่าVectorที่งบบริบทใกล้กัน. เป็นcached Ollama bge-m3 rankingของเพื่อน ไม่ใช่CPE/คำตอบLLMรอบใหม่; test76ข้อยังไม่รัน. รายงานในเครื่อง: `graph/expansions/audits/20261104-retrieval-dev/ANALYSIS.md`.

ตรวจconnectivityเพิ่มเติมแล้ว: goldที่ขาด24occurrences มีเพียง2ที่currentpathไปถึงแต่limitตัด; อีก9อยู่นอกseedversionและ13ไม่มีcurrentpathในversionเดียวกัน. Oracleเพดานcurrentpaths73.38%ไม่ใช่คะแนนค้นหาจริง; ควรทดลองทางเข้าค้นEntity/Factและตรวจidentityก่อนเพิ่มlimit/สกัดใหม่. Same-name/scope split395groupsยังไม่อนุมัติให้merge. ดูรายงานในเครื่อง `graph/expansions/audits/20261104-retrieval-dev/CONNECTIVITY.md`.

ทดลองEntity/Factentrypointแบบlexicalแล้วบนdev34ข้อ: recall76.26% สูงกว่ากราฟเดิม71.84% แต่ต่ำกว่าlexicalchunkcontrol78.19%และVector8 81.26%. ยังไม่จูนหลังเห็นผล/ไม่ใช้test76ข้อ/ไม่เพิ่มAPI/ไม่mergeหรือแก้runtime. ยังไม่รับรองว่ากราฟให้ประโยชน์เหนือtextsearch; ดู[วิธีทดลอง](evaluation/README.md#ทดลองทางเข้าค้น-entityfact-โดยตรง) และรายงานในเครื่อง `graph/expansions/audits/20261104-direct-entry-dev/ANALYSIS.md`.

ตัวสกัดปัจจุบันใช้span IDsเพื่อให้โค้ดคืนquoteจากsourceเดิม และตัวตรวจexpansionแยกจากpilot. Focus `general-facts-v2` รองรับข้อมูลเชิงบรรยาย/ติดต่อ/ขอบเขตผู้ใช้; ทดลองแก้7chunksที่เคยว่างแล้ว6ชิ้นมีfacts ส่วนสารบัญยังว่าง. ชิ้นควบคุม3/3ผ่าน แต่ยังเป็นdevelopment ไม่ใช่อนุมัติproduction/สกัดทั้งคลังอัตโนมัติ ดู [ผลและข้อจำกัด](EXPANSION.md#ตัวสกัดปัจจุบัน-source-spans-และการตรวจ-offline)

**เครื่องใหม่เริ่มที่ [QUICKSTART](QUICKSTART.md)**: ติดตั้งเฉพาะrequirementsกราฟ → `python graph/run.py build` → เปิดNeo4jด้วยComposeแยก → `python graph/run.py load`. ไม่ต้องมีAPI keyเพื่อสร้างexportเดิม

โฟลเดอร์นี้เก็บชุดสร้าง/ตรวจ/โหลดกราฟ ไม่รวมการลองschema/โมเดล/จูนคำตอบ. `build` เดิมคือfrozen pilot replay; `expand` รับเอกสารใหม่เป็นbatchแยก ยังไม่เชื่อมAPIหรือทำlifecycle/productionครบ

ส่งกราฟที่สร้างแล้วให้เพื่อน: [คู่มือสำเนากราฟ](TRANSFER.md). `transfer export` ตรวจเทียบNeo4jแล้วส่งออกJSONไฟล์เดียว; `transfer check/load` ใช้ไฟล์นั้นได้โดยไม่ต้องมีsource chunks/LLM cacheหรือเรียกLLMซ้ำ. ไม่ใช่การเปิดHybridในAPI

```text
graph/
├── build/       prepare, contracts, extract, load_graph และ common
├── data/
│   ├── inputs/  schema ที่ freeze, aliases, รายการ chunks และหลักฐานตรวจ
│   ├── results/ bundle, extraction, graph, contracts และผลโหลด Neo4j
│   ├── review/  รายงานตรวจการสร้างกราฟ
│   ├── details/ หลักฐานละเอียดที่สร้างจากผลเดิม
│   └── cache/   cache ในเครื่อง ไม่เข้า Git
├── expansions/ local cache, source reviews และ full exports (ไม่เข้า Git)
└── tests/       tests ของ build/validation/runtime integration
```

ต้นทางยังอยู่ `../data/chunks/` ไม่ย้าย ไม่แบ่ง chunk ใหม่. schema ฐานอยู่ที่ [data/inputs/schema.json](data/inputs/schema.json) ไม่ใช่ไฟล์ทดลองที่ควรนำออก. โหมด `expand` เพิ่มmetadata profile `+source-metadata-v1` เพื่อเก็บURL/วันสิ้นผล/รุ่นที่แทนที่ โดยไม่แก้frozen pilotเดิม (ดู [รายละเอียด](EXPANSION.md))

## รันจาก repository root

คำสั่งสร้างกราฟใช้เฉพาะ `graph/build/requirements.txt` ได้. เฉพาะtestsที่เชื่อมbackend/runtimeจึงต้องติดตั้ง `backend/requirements.txt` เพิ่ม; ไม่จำเป็นสำหรับเพื่อนที่ต้องการbuild/loadกราฟเดิม

```sh
python3 graph/build/prepare.py --check
python3 graph/build/contracts.py --check
python3 graph/build/extract.py --pilot --check
python3 graph/build/load_graph.py --check
PYTHONPATH=backend python3 -m unittest discover -s graph/tests -p 'test_*.py'
```

คำสั่ง `--check` ไม่อ่าน key/เรียก API/เขียน DB. ใช้ `python graph/run.py build` เพื่อสร้างผลในพื้นที่ชั่วคราว ตรวจครบก่อนสลับมาแทนชุดเดิม; ถ้าขั้นตอนใดไม่ผ่านจะไม่เผยแพร่ผลบางส่วน. คำสั่งย่อย `prepare.py`/`extract.py` เป็นเครื่องมือระดับต่ำและอาจเขียนผลทันที ไม่ใช่เส้นทางปกติของผู้ใช้ใหม่

`extract.py --pilot --extract` เรียก MiMo เฉพาะงานที่ขาดและใช้ cache จึงต้องอนุญาตข้อมูล/ค่าใช้จ่ายก่อนใช้. `load_graph.py --load` เขียนเฉพาะ Neo4j staging run ที่ตรวจแล้ว ใช้ credentials จาก `.graph-pilot.env` ที่ไม่เข้า Git; ไม่เปิด production retrieval

## อะไรยังต้องเก็บ

- `questions.json` ยังเป็น dependency จริงของตัวสกัด pilot: ใช้ข้อความคำถามเป็น focus และตรวจ snapshot เดิม ไม่ได้ส่งเฉลยให้ LLM. การตัดออกตอนนี้จะเปลี่ยน job hashes/review provenance จึงไม่ลบทิ้งเพื่อให้โฟลเดอร์ดูสะอาด
- `smoke_review.json` / `pilot_review.json` คือบันทึกแก้และตรวจหลักฐานที่ export ปัจจุบันใช้จริง ไม่ใช่การทดลอง schema
- ชุดนี้ยังเลือก24 primary +2 context +1 vector_only และ schema เดิม ไม่ได้เพิ่มความสามารถสร้างกราฟทุก1233chunksจากการย้ายไฟล์

## งานทดลองออกจาก Git

ย้ายต้นฉบับสคริปต์/ข้อมูล/tests/ผลทดลองเดิมไป `.local/graph-rag-research/` และ ignore ทั้งโฟลเดอร์แล้ว. มีผลทดสอบ LLM, schema development, retrieval/answer evaluation และ prompt revision ครบ ไม่ลบผลหรือ rewrite Git history. คำสั่ง build ด้านบนไม่อาศัย archive

ส่วน runtime ที่ backend ยังต้องใช้คงอยู่ `backend/services/{graph,hybrid_rag,query}_service.py` และ `backend/schemas/retrieval.py` ตาม architecture; `/chat/ask` ยัง Vector เดิม. ไม่ย้ายโค้ด shared มา duplicate ใน graph
