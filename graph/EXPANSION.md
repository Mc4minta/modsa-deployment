# Phase12 — สร้างกราฟจาก chunks ชุดใหม่

โหมดนี้ไม่ใช้รายการ27chunksหรือคำถาม50ข้อของpilot. ใช้ชนิดnode/เส้นเชื่อมจากschemaเดิม และเพิ่มmetadata profile `+source-metadata-v1` อัตโนมัติ รับJSONเอกสารหนึ่งไฟล์หรือdirectoryใต้ `data/chunks/` โดยแต่ละไฟล์คือเอกสารทั้งฉบับหนึ่งรุ่น

Profileนี้เก็บ `source_uri`, `topic_tags`, `content_type`, `effective_until`, `ingested_at`, `supersedes` ลงกราฟด้วย โดยไม่แก้schema/ผลตรวจpilotเดิม. `supersedes` เป็นรายการIDรุ่นที่ต้นทางระบุ ไม่ใช่การสั่งลบ/ปิดรุ่นเก่า. ไม่มีการเดาวันหรือสถานะที่ขาด. Schema hash/cache key ของexpansionเปลี่ยนจากก่อนเพิ่มprofile จึงไม่แอบนำcacheคนละschemaมาใช้และไม่เรียกAPIทดแทนอัตโนมัติ

ติดตั้งตาม [QUICKSTART](QUICKSTART.md) ก่อน ใช้เฉพาะrequirementsกราฟได้ ไม่ต้องเริ่มbackend/Chroma. `build/load` แบบpilotเดิมยังอยู่และไม่ถูกแทนที่

## ตัวสกัดปัจจุบัน: source spans และการตรวจ offline

### สถานะล่าสุด: cache ครบ 1,233 chunks แต่ยังเป็น PENDING

ตรวจต้นฉบับงานค้าง28chunksแล้ว: 11chunksคืนรูปnumeric boundที่sourceระบุชัด (20fact edits), อีก17chunksเก็บ25factsเป็นข้อความPRIMARYต้นฉบับเต็มและระบุ `SOURCE_TEXT_NEEDS_REVIEW` แทนการเดาnumeric/column interpretation. ไม่ลบfacts ไม่เปลี่ยนตัวเลขให้ตรงเฉลย และไม่อนุมัติความหมาย/สิทธิ์นโยบาย. Source-textใช้predicateกลาง; subject refsเดิมยังคงเป็นcandidateที่ต้องsemantic review ไม่ใช่การยืนยันcolumn/program mapping

งานที่เคยขาดผล1chunkสกัดใหม่สำเร็จด้วย1callที่เหลือจากงบ290เดิม (289+1): ได้3facts,5893reported tokens,provider cost$0.0007715. เก็บreservationเก่า/หลักฐานbillingของคำขอเดิมแยก ไม่สวมคำขอเดิมว่าสำเร็จ. ปัจจุบันไม่มีcacheขาด/failedหรือinitial reservationค้าง. `--check --reuse-mimo-cache`รายงาน1233ready พร้อมแจ้งAI-curated28/PENDINGและnumeric deferred17 ไม่ใช่semantic approval100%

Coverageปัจจุบัน: `CANDIDATES_UNREVIEWED`1201 / `SOURCE_TEXT_NEEDS_REVIEW`17 / `EMPTY_NEEDS_REVIEW`15. AI source reviewอยู่`graph/expansions/reviews/<request_hash>.json` (ignored) และถูกใช้เฉพาะเมื่อrequest hash+raw record hash+fact before hashตรงทุกส่วน. Source scalarแก้ได้เฉพาะboundของปริมาณเดิมที่ตรวจsourceซ้ำผ่าน ไม่อนุญาตเปลี่ยนquantityหรือใช้EQจากการไม่พบbound. Source textคืนquoteเดิมเต็มพร้อมunresolved; raw responses/cacheไม่ถูกเขียนทับ. เปลี่ยนresponse/sourceแล้วต้องreviewใหม่ ไม่แอบใช้reviewเก่า

Export manifestแยกraw response hash,review hashและderived record hash พร้อมPENDING/deferred status. หากย้ายเครื่องเพื่อreplayผลสกัดเดียวกันต้องนำcacheและreviewsที่อนุญาตไปด้วย; Gitไม่ส่งข้อมูลignoredเหล่านี้ หรือส่งสำเนากราฟภายหลังสร้าง/ตรวจ/โหลดตาม[TRANSFER](TRANSFER.md). Testsgraph204/backend26ผ่าน, frozenpilot134nodes/231edgesเดิม. รายงานรายละเอียดเฉพาะเครื่องอยู่`graph/expansions/audits/20261104-offline-failures/FIX_RESULTS.md`

**Full exportสร้างและตรวจไฟล์จริงแล้ว4พ.ย.2026**: batch `b34295eea9bd0b6444e60d6910f7d1e1449afdd2b7480a8dcb85acaa6f1c50a8`, 71documents/1233chunks,7911nodes/17004edges/3253Fact nodes. ไฟล์อยู่`graph/expansions/batches/<batch_id>/graph.json` พร้อม`EXPORT_REVIEW.md`/`export_verification.json`. ตรวจreplayตรงกัน, quote4215รายการตรงsource, input/cache/review1332ไฟล์hashไม่เปลี่ยน. Buildใช้0API calls/0tokensใหม่. ทุกnodeยังPENDING/retrieval_enabled=false; 17source-text/15emptyยังเป็นข้อจำกัดด้านคุณภาพ ไม่ใช่ผ่านsemanticทั้งหมด

**Neo4j stagingโหลดและตรวจจริงแล้ว4พ.ย.2026**: ครั้งแรกเพิ่ม7911nodes/17004edges, โหลดซ้ำหลังcommitเพิ่ม0/0. อ่านกลับทั้ง71runsเทียบexportครบ; ทุกnodeของbatchยังPENDING/retrievalปิด. Pilot134/231และข้อมูลนอกbatchทั้งหมด580/821fingerprintไม่เปลี่ยน. ใช้0LLM calls/0tokensใหม่ ไม่แก้Chroma/ไม่เปิดHybrid. ผลอยู่`NEO4J_STAGING.md`/`load_verification.json`ในbatchเดียวกัน; `load_first.json`เก็บผลสร้างจริง ส่วน`load.json`ล่าสุดเป็นรอบซ้ำ0/0. สถานะนี้ไม่ใช่production approval; ขั้นถัดไปทดสอบretrievalและanswer eval

### ล่าสุดหลังรอบซ่อม: source-layout-v4

ทวนทั้งคลังแบบofflineหลังตรวจ47chunksที่ยังไม่ผ่าน: เพิ่มคำเปรียบเทียบไทย/อังกฤษและqualifiersที่มีหลักฐานตรง (`ไม่ต่ำกว่า`, `not exceed`, `maximum of`, `ร้อยละ/เดือนละ` ฯลฯ), ใช้stdlib HTMLParserทำnumeric viewเพื่อไม่อ่านHTML tags/attributesเป็นเครื่องหมาย/ตัวเลข และคงtable-row boundaries. Evidence/source-span contractและinitial prompt/hashไม่เปลี่ยน; ไม่แก้raw outputเพื่อให้ผ่าน. ตารางmerged cellsที่ต้องอาศัยcolumn mappingและMarkdownที่ขาดหัวคอลัมน์ยังfail closed. Frozen pilotไม่เปลี่ยน

กู้คืน22จาก47โดยไม่สกัดเพิ่ม แต่ปฏิเสธผลที่เคยผ่านเพิ่ม3: ยอดล่าสุด1204ผ่านlocal validation (1189มีfacts/15empty-needs-review), 28ยังต้องsource review. ตรวจประวัติคำขอเดิม1ชิ้นแล้วพบprovider billingแต่ไม่มีcompleted output; คงinitial reservationพร้อมdispatch_auditกันส่งซ้ำโดยไม่ได้อนุญาต. จึงไม่ใช่สถานะunknown costอีกต่อไป แต่ยังขาดผลสกัดและไม่อนุญาตfresh generationอัตโนมัติ. ผลรายละเอียดอยู่`graph/expansions/audits/20261104-offline-failures/FIX_RESULTS.md`ในเครื่อง (ignored)

Testsล่าสุดgraph200/backend26ผ่าน; full-corpus replayไม่เปลี่ยนhash cacheดิบ1232ไฟล์; frozenpilot134nodes/231edgesเดิม. Local validationไม่ใช่semantic approval และยังไม่สร้างfull-batch export/โหลดNeo4jจากชุดนี้. หัวข้อv3และผลจำนวนก่อนหน้านี้ด้านล่างเป็นประวัติก่อนv4 ไม่ใช่ยอดล่าสุด

### อัปเดต 4 พฤศจิกายน 2026: ตรวจ cache เดิมก่อนใช้ API ซ่อม

ตัวตรวจ expansion ปัจจุบันคือ `source-layout-v3` (ไม่แก้ frozen pilot): รองรับ comparator ที่มี newline/`<br>` และ `ภายใน/within`, ตรวจ negation และกรณีเลขเดียวกันหลายขอบเขตแบบ fail closed, รองรับชื่อระดับการศึกษาไทย/อังกฤษ/ตัวย่อที่มีหลักฐานตรงจริง, และผูกความประมาณกับค่าตัวเลขแทนการจับ `งบประมาณ` หรือค่าคนละหน่วย. ปีของ Offering ยังต้องมีป้ายปีการศึกษาจริง ไม่รับวันที่ปรับปรุงหรือชื่อไฟล์; round ไม่ใช่ภาคการศึกษา

Scalar ที่มี inclusivity flag ซ้ำกับ operator (เช่น GTE + lower_inclusive=true โดยไม่มีค่าขอบเขต) ถูกคืนรูปเทียบเท่าเป็น scalar พร้อม audit `redundant-scalar-bound-v1` เฉพาะ derived validation; ไม่เปลี่ยนตัวเลข/operator/หลักฐานหรือ cache ดิบ. Flags ที่ขัดแย้งและ range fields ที่มีค่าจริงยังปฏิเสธ. Scholarship Entity ต้องมีหลักฐานของทุน ไม่ยอมรับตารางค่าธรรมเนียมเป็นทุนเพียงเพราะชื่ออยู่ใน source; การตรวจนี้ยังไม่ใช่ semantic approval ทุกชนิดข้อมูล

Initial prompt/cache identity `general-facts-v2` คงเดิมเพื่อไม่ส่งทั้งคลังซ้ำ. **เฉพาะ bounded repair** ใช้ `typed-scope-v2`: กำชับ fee/program ไม่ใช่ทุน, Offering เฉพาะทุนจริง, ปีการศึกษาไม่ใช่วันที่เอกสาร และ wire schema แยก scalar/BETWEEN. Attempt hash บันทึก payload ซ่อมจริง; ไม่สวมผลเก่าเป็น prompt ใหม่. Repair reservation เดิมยังใช้สิทธิ์สูงสุดหนึ่งครั้งต่อ job ไม่ล้างสิทธิ์เพียงเพราะแก้ prompt. เก็บทั้ง cache ดิบก่อนซ่อมและผลตรวจที่ใช้ซ่อมใน content-addressed archive

มี reservation สำหรับ initial request ด้วย: `cache/initial/<request_hash>.json` สถานะ RESERVED หมายถึงยังไม่ทราบผล จึงกันทั้ง initial resend และ repair จนตรวจ journal/provider ก่อน. `--check` ไม่สร้าง reservation. อย่าลบไฟล์เพื่อฝืนส่งซ้ำ; cache/journal/reservations เป็นข้อมูลในเครื่องที่ Git ไม่ส่งต่อ

ผลก่อนใช้ API ซ่อม: จาก 1,233 chunks พบ 943 ผ่าน local validation, 288 failed, 1 ต้อง initial ใหม่เพราะ MiMo เดิมไม่ผ่านเกณฑ์ใหม่, 1 unknown dispatch ที่กันไว้. กู้คืนงานค้างเดิม 91 ชิ้นโดยไม่เรียก API; ปฏิเสธผลที่เคยผ่านเพิ่ม 3 ชิ้น และไม่ reuse MiMo อีก 1 ชิ้นที่พบว่า EQ ทำให้ขอบเขต `ภายใน` หาย. ยอดไม่ใช่คะแนนความถูกต้องเชิงความหมาย. Tests: graph195/backend26 ผ่าน, frozen pilot134nodes/231edgesเดิม. สถิติ/หลักฐานเฉพาะเครื่องอยู่ `graph/expansions/audits/20261104-offline-failures/` (ignored); รอบซ่อมมีงบแยกจาก initial extraction และยังต้องอนุญาตก่อนเรียก

### ประวัติและข้อจำกัดของ source-span extraction

Focusปัจจุบันคือ `general-facts-v2`: ยอมรับข้อมูลเชิงบรรยาย/ข้อมูลติดต่อ/URLบริการ/หน้าที่/ขอบเขตผู้ใช้และข้อยกเว้น ไม่จำกัดเฉพาะตัวเลขหรือทุน. โทรศัพท์ อีเมล ที่อยู่ URL เป็น `value_text` ไม่แปลงเป็นตัวเลขหรือเดาข้อมูลที่ขาด. สารบัญ/รายการนำทางล้วนไม่ถูกบังคับสร้างfacts. เปลี่ยนpromptจริงทำให้request/cache keyใหม่; responseรุ่นเก่ายังอยู่ ไม่เขียนทับหรืออ้างว่าเป็นผลpromptใหม่. `MIMO_FOCUS`เก็บข้อความhistoricalเดิมไว้คำนวณkeyของMiMoโดยเฉพาะ เพื่อไม่ให้การแก้focusใหม่ทำให้cacheเดิมหาไม่เจอ. Manifestระบุfocus_versionแยกตามresponse

ผลติดตามcoverageรอบล่าสุด: ทดสอบ7chunksที่เคยไม่มีfact +3positive controls +2ตัวอย่างใหม่ รวม12คำขอ ไม่มีrepair. 6จาก7ชิ้นเดิมสกัดfactsได้ อีก1เป็นสารบัญและยังว่าง; positive controls3/3ผ่าน; ตัวอย่างใหม่1ชิ้นผ่าน อีก1เกิดConnectionResetErrorและไม่ยิงซ้ำ. ผลAPIที่ตอบกลับ11/11ผ่านlocal validation มีfacts10ชิ้น ไม่พบtruncation. ใช้60165tokensที่รายงาน ประมาณ$0.007917ตามราคาเต็มก่อนdiscount/fee/tax; คำขอเครือข่ายล้มเหลวไม่มีusage จึงไม่ทราบtokens/costของคำขอนั้น ไม่คิดเป็น0. ผลอยู่ `graph/expansions/comparisons/general-facts-20261103T084822/`

ผลดังกล่าวยืนยันว่าแก้coverage gapที่พบในตัวอย่างนี้ได้ ไม่ใช่การรับรองความครบ/ความถูกต้องทั้งคลังหรืออนุมัตินโยบาย. การเพิ่มfactsไม่ใช่เป้าหมายสำหรับทุกchunk และไม่มีการโหลดNeo4j/เปิดHybridจากการทดสอบนี้

`expand` ใช้สัญญา `source-spans-v1`: โค้ดแบ่งPRIMARY/CONTEXTเป็นparagraphหรือแถวMarkdown table พร้อมID/ตำแหน่งตัวอักษร. ส่งเฉพาะข้อความสำหรับอ่าน (ปรับช่องว่าง/`<br>` โดยไม่แก้คำ) และให้LLMเลือก `evidence[].span_id`, `Fact.raw_span_id` แทนการพิมพ์quoteซ้ำ. โค้ดตรวจID/PRIMARY/evidenceแล้วดึงparagraphหรือแถวเต็มจากsourceเดิมกลับเป็นquote/raw_text รวมข้อยกเว้น. ชื่อentityและvalue_textยังต้องตรงกับหลักฐาน ไม่ยอมรับIDปลอมหรือfactที่มีเฉพาะCONTEXT

ตัวตรวจexpansionใช้ `source-layout-v2` แยกจากfrozen pilot: คืนรูปช่องว่าง/HTML line breakโดยมีaudit, คืนช่องว่างในชื่อไทยโดยไม่เปลี่ยนตัวอักษร, ตรวจข้อยกเว้นทั้งfact/rule, ผูกcomparatorกับตัวเลข/หน่วย, รองรับ`ขึ้นไป`, และตรวจคำว่า`ประมาณ`ตามคอลัมน์ตาราง. ไม่ผ่อนการตรวจคำ/ตัวเลข/negationที่หายจริง. การคืนชื่อไทยไม่อนุญาตการต่อคำอังกฤษหรือตัวเลข เช่น `not able`→`notable` หรือ `1 0`→`10`

Cacheที่ผ่านfalse-negativeจากตัวตรวจเก่าทวนใหม่แบบofflineได้ ไม่ต้องส่งLLMซ้ำ. `cached()`คืนผลตรวจใหม่ในหน่วยความจำพร้อม `revalidation.source_record_hash`/profile; ไม่เขียนทับresponse/cache/usageเก่า ไม่ลบrepair reservation ไม่เปลี่ยนชื่อโมเดล. ผลที่ยังผิดจริงไม่ผ่านและยังต้องตรวจตามเดิม. Request identityขึ้นกับprompt/source/wire contract ไม่เพิ่มการเรียกAPIเพียงเพราะปรับตัวตรวจ; เปลี่ยนprompt/wire contractจริงจะได้keyใหม่

`coverage_status=EMPTY_NEEDS_REVIEW` หมายถึงไม่มีfact ไม่ใช่รับรองว่าต้นฉบับไม่มีข้อมูลที่สกัดได้. `CANDIDATES_UNREVIEWED` หมายถึงมีcandidatefactsแต่ยังไม่อนุมัติsemantic quality. ค่าเหล่านี้อยู่ในcache-derived result/export manifest ไม่เปลี่ยนสถานะgraphเป็นVERIFIED/ACTIVE

ผลbaseline development24chunks/6ประเภท ก่อนเปลี่ยนfocus วันที่3พฤศจิกายน2026: รอบAPIครั้งเดียวต่อchunk ไม่มีrepair ใช้118795tokens (input86876/output31919), เวลารอAPIรวม251.24s, ไม่พบtruncation. ตัวตรวจv1ผ่าน20/24; หลังแก้บั๊กตัวตรวจทั่วไปและreplayโดยไม่เรียกAPIเพิ่ม v2ผ่าน24/24 แต่มีfactsเพียง17chunks อีก7chunksว่าง/ไม่มีfactและต้องตรวจcoverage ไม่ใช่คะแนนsemantic accuracy100%. ช่องว่างด้านข้อมูลติดต่อ/audience exclusionนำไปทดสอบfocusใหม่ตามผลติดตามด้านบน; ไม่แก้response baselineย้อนหลัง

ค่าtokenเต็มราคาประมาณ$0.0150714สำหรับรอบ24คำขอ หรือ$0.0008866ต่อchunkที่มีfactและผ่านlocal validation (ไม่ใช่ต่อคำตอบที่ยืนยันว่าถูก). ไม่หักcache discount/ไม่รวมfee/tax/ไม่ใช่ยอดbill. ผลสรุปและmanifestอยู่ `graph/expansions/comparisons/source-spans-dev-20261103T080304/` ซึ่งGit ignoreไว้. ชุดเลือกใช้source/ประเภทเอกสาร ไม่ส่งคำถามหรือเฉลยevalให้extractor. ข้อมูลใหม่/ตารางซับซ้อน/เงื่อนไขข้ามparagraphหรือchunkยังต้องประเมินต่างหาก

## 1. วางแผนโดยไม่ส่งข้อมูล

```sh
python graph/run.py expand --input data/chunks/fees --check
```

แสดงจำนวนเอกสาร/chunks/คำขอสกัดที่ยังขาด ไม่อ่านAPIkey ไม่สร้างไฟล์ ไม่เชื่อมDB. เลือกไฟล์เดียวแทนdirectoryได้ เลือกเอกสารทั้งฉบับเสมอ ไม่ตัดแค่บางchunksให้identityของรุ่นเดียวกันเปลี่ยนตามbatch

รูปแบบJSONใช้schemaเดิมของทีมData: `doc_id`, `metadata`, `chunks[{chunk_id,content,page}]`. ต้องมีdoc_id/chunk_idไม่ซ้ำและcontentไม่ว่าง; ไม่รับsymlinkออกนอก `data/chunks/`. ไม่ทำOCRหรือแบ่งchunksใหม่

## 2. สกัดเมื่ออนุญาตข้อมูลและค่าใช้จ่ายแล้ว

ตั้ง `OPENROUTER_API_KEY` ใน `.env` ที่rootหรือenvironment (รองรับ `backend/.env` เป็นfallback). โหมด `expand` ใช้ `meta/muse-spark-1.3-contributor` ที่ `https://openrouter.ai/api/v1` ไม่อ่าน `MIMO_API_KEY` และไม่เปลี่ยนโมเดลตอบคำถาม/embedding ของbackend. Frozen pilot `extract.py --pilot` ยังใช้MiMoเหมือนเดิม

รุ่น Contributor ระบุว่าprompt/ผลลัพธ์อาจถูกใช้ปรับปรุงผลิตภัณฑ์Meta ต้องยืนยันสิทธิ์ส่งข้อมูลก่อนเรียกจริง: [เงื่อนไขโมเดล](https://openrouter.ai/meta/muse-spark-1.3-contributor). ไม่มีการเปิดสิทธิ์trainingในบัญชีให้อัตโนมัติ. ส่งJSON schemaเดิมและกำหนด `require_parameters=true`, `allow_fallbacks=false` เพื่อไม่ให้ข้ามstructured outputหรือเปลี่ยนproviderเอง; endpointไม่รองรับ/สิทธิ์ไม่พอจะหยุด ไม่แอบใช้MiMoแทน

```sh
python graph/run.py expand --input data/chunks/fees --extract --max-calls 126
```

126เป็นเพียงตัวอย่างจากจำนวนchunksในหมวดfeesปัจจุบัน ให้ใช้จำนวนmissingจาก `--check` ของชุดที่เลือกจริง ห้ามเพิ่มงบทั้งคลังโดยไม่ตรวจ scope. ถ้างบไม่พอจะหยุดก่อนส่งAPIทั้งหมด. ค่าเริ่มต้นไม่มีautomatic retry/model repair/provider fallback;หนึ่งattemptต่อchunkที่ขาด หากล้มเหลวจะหยุดและเก็บcacheที่สำเร็จไว้. งานที่ใช้repairไปแล้วจะไม่ถูกวนสกัดใหม่อัตโนมัติ

### ทำต่อจากผล MiMo เดิมโดยไม่สกัดงานที่ผ่านซ้ำ

```sh
python graph/run.py expand --input data/chunks --check --reuse-mimo-cache --repair-once
```

`--reuse-mimo-cache`เป็นopt-in: รับเฉพาะcacheที่ตรงsource/version/context/schema/promptเดิมทุกส่วน, ระบุโมเดลMiMoเดิม, ไม่มีerror และผ่านตัวตรวจหลักฐานปัจจุบันซ้ำ. ไม่ย้าย/เขียนทับ/เปลี่ยนชื่อโมเดลในresponseเดิม. Cacheที่ขาด/เปลี่ยนระหว่างใช้งานจะหยุด ไม่ยิงโมเดลใหม่ภายใต้keyเก่า. ถ้ามีOpenRouter cacheของงานนั้นอยู่แล้วจะใช้ของใหม่ก่อน

ผลตรวจofflineวันที่3พฤศจิกายน2026: 71เอกสาร/1233chunks ใช้MiMoเดิมได้111chunks เหลือ1122chunks (1075ยังไม่เริ่ม +47ผลเดิมไม่ผ่าน). เพดานเมื่อเปิดrepairคือ2244calls. MiMoที่ไม่ผ่านไม่ถูกนำมาใช้เป็นผลสำเร็จหรือส่งให้Museซ่อมต่อ; เป็นinitial requestใหม่ของMuseด้วยkeyใหม่ และมีสิทธิ์repairใหม่สูงสุด1ครั้งต่อkey. ประวัติ/reservation/ต้นทุนMiMoเดิมยังอยู่ครบ จึงไม่ใช่การล้างสิทธิ์ซ่อมMiMoเดิม

ผลจะเป็น **mixed-model build** ไม่ใช่ผลMuseล้วน; exportมี `documents[].extractions` ระบุchunk, model, endpoint, request hash และresponse hashเพื่อaudit. ต้องระบุflagนี้เหมือนกันทั้ง `--check`, `--extract`, `--build`, `--load`. ถ้าไม่ระบุจะใช้เฉพาะOpenRouter cacheและวางแผนสกัดส่วนที่ยังไม่มีใหม่ ไม่ลบMiMo cache. Checkไม่ใช่การอนุญาตส่งข้อมูล/ใช้งบ

### Repair แบบจำกัด (opt-in)

โหมดประหยัด (ค่าปัจจุบัน): Museรองรับreasoningแบบบังคับ จึงปิดไม่ได้; ตั้ง `reasoning.effort=minimal` ซึ่งเป็นระดับต่ำสุดที่APIระบุ และเพดานรวม `max_tokens=6000`. เพดานนี้รวมreasoningกับJSON ไม่ใช่การจ่ายเต็ม6000ทุกคำขอ. ยังต้องทดสอบว่าJSONจบและผ่านหลักฐานจริง ไม่รับรองว่าถูกที่สุดต่อผลสำเร็จก่อนวัดผล. ไม่ลดschema/หลักฐานเพื่อประหยัด และไม่เปลี่ยนโมเดล

เพื่อไม่จ่ายซ่อมอัตโนมัติ ให้ใช้คำสั่งโดย **ไม่ใส่ `--repair-once`**:

```sh
python graph/run.py expand --input data/chunks --check --reuse-mimo-cache
# หลังทดสอบชุดเล็กผ่านและอนุญาตงบทั้งคลังแล้ว ใช้จำนวนmissingล่าสุด:
python graph/run.py expand --input data/chunks --extract --reuse-mimo-cache --max-calls 1122
```

โหมดนี้หยุดเมื่อคำขอแรกไม่ผ่าน จึงไม่วนทั้งคลังหรือจ่ายrepairเพิ่มเอง. การเปลี่ยนreasoningทำให้request/cache keyใหม่; ไม่ลบประวัติ/ต้นทุนหรือreservationเก่า และยังใช้ผลMiMo111chunksที่ผ่านการตรวจซ้ำได้. ตัวสกัดเก็บreasoning_detailsสำหรับส่งกลับโดยไม่แก้ไขเมื่อเปิดrepair และเก็บreasoning_tokens/visible_tokensเมื่อproviderรายงานในusage; สถิติ `reasoning_usage` ระบุจำนวนคำขอที่ขาดรายละเอียด ไม่เดาว่าเป็น0. ไม่พิมพ์reasoning_detailsลงjournalสถิติ

ผลทดสอบจริงโหมดประหยัดวันที่3พฤศจิกายน2026 (ยังไม่ผ่านเพื่อรันทั้งคลัง):

| ขั้น | ขอบเขต | เวลารอ API | Output / reasoning tokens | ผล |
| --- | --- | ---: | ---: | --- |
| minimal/6000 | AcademicCalendar2026-2569TH2#0006 | 22.70s | 2569 / 1422 | ตอบจบ แต่ใส่ค่าตัวเลขทั้งช่องnumberและtext |
| เพิ่มคำสั่งรูปแบบตัวเลขทั่วไปในsystem prompt | chunkเดิม | 12.37s | 2028 / 874 | ตอบจบ ไม่มีnumeric-format errorเดิม แต่ยังมีinvalid_evidence/invalid_subject_refs/truncated_source_exception |

ใช้2คำขอ ไม่ได้repairอัตโนมัติ ไม่ใช้คำขอที่3หลังไม่ผ่าน. รวมprompt8814/output4597/total13411tokens; ราคาคิดเต็มตามtoken ratesที่ตรวจไว้ประมาณ$0.0018008 ไม่หักprompt cache จึงไม่ใช่ยอดbillยืนยัน. ผลอยู่ในbatch `3072fc87...` / `2e1a0c1e...` ใต้expansions/offlineของแต่ละbatch พร้อมstats/requests journal. ไม่มีผลใหม่ผ่านvalidation; ยังคง111ready/1122pending ไม่exportกราฟหรือโหลดNeo4j. ยืนยันได้เฉพาะแก้การถูกตัดใน2คำขอนี้ ไม่รับรองคุณภาพทั้งคลัง และยังสรุปไม่ได้ว่าข้อผิดพลาดหลักฐานเกิดจากลดreasoningโดยตรงเพราะไม่ใช่controlled evaluation

คำสั่งด้านล่างเป็นตัวเลือกเมื่ออนุญาตค่าซ่อมโดยเฉพาะ ไม่ใช่โหมดประหยัดเริ่มต้น:

```sh
python graph/run.py expand --input data/chunks --check --reuse-mimo-cache --repair-once
# รันบรรทัดนี้เฉพาะหลังอนุญาตข้อมูล/งบแล้ว และตรวจเพดานจาก check ล่าสุด:
python graph/run.py expand --input data/chunks --extract --reuse-mimo-cache --repair-once --max-calls 2244
```

`--repair-once`อนุญาตให้แก้ผลที่validationไม่ผ่าน/JSONผิด/คำตอบถูกตัด โดยส่งsourceเดิม+schema+ผลเดิม+validation feedbackกลับให้โมเดลเดิม **ไม่เกิน1ครั้งต่อjob keyข้ามทุกinvocation**. ไม่ส่งเฉลยeval. ผลเดิมเก็บใน`cache/attempts/`แบบcontent-addressedและreserveสิทธิ์ใน`cache/repairs/`ก่อนHTTP; หากถูกinterruptระหว่างrepair จะไม่ส่งซ้ำเองเพราะอาจเสียโควตาไปแล้ว. ไม่ลดvalidationหรือแต่งค่าตัวเลข/quoteเพื่อให้ผ่าน

งบต้องครอบคลุมworst case (งานใหม่สูงสุด2calls; งานfailedเดิมที่ยังrepairได้1call) ตรวจงบก่อนAPIและนับทั้งinitial/repair. ผลจากrepairที่ผ่านนำไปใช้เป็นcacheปัจจุบัน; ถ้าไม่ผ่านจะเก็บงานค้างแล้วทำงานอื่นต่อ จบรอบเขียน`needs_review.json`และไม่เผยแพร่กราฟ/ไม่โหลดDBจนทุกงานผ่าน. API/สิทธิ์/โควตา/transport errorหยุดทันที ไม่มีretryหรือprovider fallback. ห้ามลบreservationเพื่อบังคับยิงซ้ำโดยไม่ตรวจjournalและอนุญาตงบใหม่

ส่งเฉพาะPRIMARYกับchunkแรก/เพื่อนบ้านใกล้เคียงของเอกสารรุ่นเดียวกันเพื่อscope ไม่ส่งเฉลยหรือข้อมูลจากคำถามpilot. ทุกข้อเท็จจริงต้องมีquoteจากPRIMARYและผ่านตัวตรวจschema/ตัวเลข/ข้อยกเว้นเดิม. แต่quoteตรงไม่ได้รับรองความสัมพันธ์เชิงความหมายหรือสิทธิ์ตามนโยบาย

## 3. สร้างซ้ำจากcache / ตรวจผล

```sh
python graph/run.py expand --input data/chunks/fees --build
```

คำสั่งนี้ไม่เรียกAPI. ผลอยู่ `graph/expansions/batches/<batch_id>/graph.json` และREADMEสรุปแต่ละเอกสาร. JSONรวม source/version, source quotes, unresolved notes และrun_idที่ต้องใช้ตรวจ. โฟลเดอร์expansionsทั้งหมดไม่เข้าGit รวมcacheและผลLLM; เพื่อนต้องสกัดของตนเองหรือรับผลที่ได้รับอนุญาตแยกต่างหาก

เอกสารเดิมที่inputs/model/prompt/schemaเหมือนเดิมใช้cacheซ้ำ. เพิ่มเอกสารใหม่ในbatchไม่เปลี่ยนrunของเอกสารเดิม. เปลี่ยนเนื้อหาเอกสารหนึ่งฉบับสร้างversionใหม่และสกัดใหม่เฉพาะฉบับนั้น (ทุกchunkของรุ่นนั้น) ไม่สกัดทั้งคลังใหม่

### Offline statistics

ทุกคำสั่ง `--extract`, `--build`, `--load` บันทึกผลการวัดแยกแต่ละ invocation ที่ `graph/expansions/batches/<batch_id>/offline/<run_id>/` โดยไม่แก้cache key/ผลpilotเดิม. `--check` ยังไม่เขียนไฟล์หรืออ่านkey

- `README.md`: สรุปเวลา, cache hits, คำขอสำเร็จ/ล้มเหลว และความครบของtokens
- `stats.json`: metadataเครื่อง/โมเดล/endpoint, เวลารวมและแต่ละphase, จำนวนงาน/HTTP attempts, tokensที่providerรายงาน และสาเหตุความล้มเหลวแบบไม่ใส่ข้อความerrorจากprovider
- `requests.jsonl`: intentที่flushลงdiskก่อนเรียกแต่ละงาน และoutcomeพร้อมusageก่อนเผยแพร่cache. ไม่ใส่key/prompt/ข้อความเอกสารในlogสถิติ

Usageที่ไม่มีหรือไม่ครบคือ **ไม่ทราบ** ไม่ใช่0tokens/0cost. `reported_tokens`รวมเฉพาะcountersที่APIคืน ต้องดู `usage_complete` และจำนวนrequestsที่usageขาดร่วมด้วย. หากprocessถูกkillแบบไม่ผ่านfinally อาจเหลือstatsสถานะRUNNING; journalยังเก็บeventsที่flushแล้ว และintentที่ไม่มีoutcomeต้องถือว่าการส่งHTTP/การคิดtokensยังไม่ทราบ ไม่รับรองว่าไม่ได้ใช้โควตา

`confirmed_http_attempts`นับการเริ่มเรียกHTTP client ไม่ใช่การยืนยันว่าproviderได้รับหรือคิดเงินแล้ว; TLS/DNS errorจึงอาจมีattemptแต่ไม่มีHTTP status/usage. ถ้าพบcertificate error ให้ติดตั้งCA bundleที่เชื่อถือได้หรือกำหนด `SSL_CERT_FILE` ให้ถูกต้อง ห้ามปิดcertificate verification. การรันจริงครั้งแรกบนmacOSนี้ใช้CA bundleจากPython environmentที่มีอยู่ หลังตรวจTLS handshakeผ่านแล้ว

เวลาดึงข้อมูล/validate/cache/journalอยู่ในphaseextract; packageรวมการvalidateซ้ำและexport; loadรวมการตรวจreadback. เวลารวมรวมmeasurement I/Oแต่ไม่รวมinvocationก่อนหน้า/ช่วงพักระหว่างresume. รันซ้ำจากcacheไม่ใช่cold build. ต้องรวมทุกรอบเมื่อรายงานต้นทุนretry; ไม่มีการประมาณราคาเงินหรือGPU-secondsของผู้ให้บริการจากเวลารอAPI. Journalและstatsแยก`initial`/`repair`; จำนวนattemptที่ล้มเหลวไม่เท่าจำนวนchunksค้าง เพราะrepairอาจแก้สำเร็จภายหลัง. โหมดปกติหยุดเมื่อvalidation error; โหมด`--repair-once`เก็บงานที่ยังไม่ผ่านเป็นรายการตรวจ แต่ไม่ข้ามไปexportกราฟบางส่วน

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

รันMiMoจริงวันที่2พฤศจิกายน2026หยุดที่HTTP429 หลังแตะ158chunks: ผ่าน111และค้าง47; ยังไม่เริ่ม1075. รอบbulkมี280attempts (157initial/123repair) รายงาน2357823tokensและมี1attemptที่ไม่มีusage; ยังมีinvocationก่อนหน้าที่ต้องรวมในการรายงานต้นทุนทั้งหมด. ยังไม่มีfull-batch graph export/โหลดNeo4jจากรอบนี้ และยังไม่ได้รับรองsemantic quality/coverageทั้งคลัง

ผลsmokeวันที่3พฤศจิกายน2026: ส่งจริง1คำขอด้วยPRIMARY1chunkและCONTEXT3chunks ได้HTTP404 ไม่มีusage/ผลสกัดคืนมา ไม่repairและไม่โหลดNeo4j. ตรวจGET `/models` แยกอีก1ครั้งได้HTTP200 (415models) แต่ไม่พบ `meta/muse-spark-1.3-contributor`; พบ `meta/muse-spark-1.3` ซึ่งเป็นคนละรุ่น จึงไม่สลับให้อัตโนมัติ. เก็บstatsและ `model_check.json` ในbatch `bec6d730982a49c8f50c1f3b85d6d973b3a08aa23cbe2c1df711a609cd6142cd` ใต้ `offline/20261103T063501-c4039b465773/`. ทั้งคลังยังค้าง1122chunks; ยังไม่ยืนยันสิทธิ์เรียกgeneration/ความเข้ากันได้ของJSON schema/ต้นทุนหรืออัตราผ่านของMuse และusageที่ไม่คืนมายังไม่ทราบ ไม่สรุปว่า0tokens

รอบแก้reviewเพิ่มtestsสำหรับcomparatorsที่ผูกกับตัวเลขเป้าหมาย (ไม่ใช้คำขั้นต่ำ/ไม่เกินจากทั้งก้อน), metadata export และการตรวจนอกbatch2รอบแม้มี71เอกสาร. Testsเหล่านี้ไม่เรียกCloudและไม่เขียนNeo4jจริง
