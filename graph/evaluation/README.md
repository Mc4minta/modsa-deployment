# Offline Graph retrieval

ทดสอบตัวเดินกราฟเดิมใน `backend/services/graph_service.py` จาก full export ที่ตรงกับผลอ่านกลับ Neo4j staging โดยไม่เชื่อมฐาน/เรียก LLM/embedding/Chroma หรือเปิด Hybrid ใน API. ใช้ backend dependencies สำหรับ `langchain_core`.

ใช้ `data/evaluation/eval_311026.json` **เฉพาะ dev 34 ข้อ**; ไม่รัน test 76 ข้อ. Gold ใช้ให้คะแนนหลังค้นหาเท่านั้น. นี่คือ replay ของ Vector ranking ที่เพื่อนเก็บไว้ด้วย `bge-m3:latest` ไม่ใช่การรัน CPE ใหม่และไม่วัดคุณภาพคำตอบ.

```sh
python3 graph/evaluation/retrieve.py \
  --export graph/expansions/batches/<batch_id>/graph.json \
  --baseline /absolute/path/to/friends/eval_runs/base/rag_outputs.jsonl \
  --output graph/expansions/audits/<new-run-name>
```

ไฟล์ข้าง export ต้องมี `load_verification.json` ที่มี SHA/content hashes ของ batch นั้น. ตรวจ source content hash, chunk content/page และ baseline retrieved content/source ตรงกันทั้งหมดก่อน replay. ไม่อ่าน answers จาก log มาใช้ค้นหา. ไม่เปิด Chroma ของเพื่อนและไม่แก้ข้อมูลต้นฉบับ. ผลถูกเขียนหลังรันครบเท่านั้น; ปฏิเสธ output directory เดิมเพื่อเก็บประวัติ.

เทียบ 4 วิธีโดยไม่ rerank/filter: Vector4, Vector8 (งบบริบทสูงสุดเท่ากัน), Vector4+adjacency เพิ่มไม่เกิน4 และ Vector4+graph เดิมเพิ่มไม่เกิน4. เดินกราฟภายใน document version เดียว; ไม่มี entity resolution ข้ามเอกสาร. การทดสอบนี้ไม่ผ่าน scope filter ของ pilot เพราะกำลังวัดผลเพิ่มจากกราฟอย่างเดียว ไม่ใช่คะแนน Hybrid pipeline ที่เปิดใช้งานจริง.

ผลอ่านสั้นอยู่ `RESULTS.md`, รายข้อ/paths/metrics/code hashes อยู่ `results.json`. ทั้งสองเป็นข้อมูลในเครื่องใต้ ignored `graph/expansions/`, ไม่ส่งต่อด้วย Git. Recall เป็น macro average บนข้อ answerable ที่มี gold; ข้อไม่มี gold เป็น N/A. Precision หารด้วยงบบริบท4/8 ไม่ใช่จำนวนที่ดึงได้จริง. คะแนน exact gold IDs ไม่ใช่ semantic relevance หรือ Fact accuracy.

ผลรอบ 4พ.ย.2026 อยู่ `graph/expansions/audits/20261104-retrieval-dev/`: Vector4 recall64.15%, Graph4+4 recall71.84%, Vector8 recall81.26%; Graphมี recallเท่า adjacency-only. จึงยังไม่มีหลักฐานว่าตัวเดิน semantic graph ปัจจุบันช่วยเหนือ Vector ที่งบใกล้กัน. ดู `ANALYSIS.md` ในโฟลเดอร์ผลก่อนตัดสินใจปรับระบบ; ยังไม่อนุมัติ production.

```sh
PYTHONPATH=backend python3 -m unittest discover -s graph/tests -p 'test_retrieval_replay.py'
```

## ตรวจว่าติดที่โครงสร้างหรือการเลือกผล

`connectivity.py` ตรวจกราฟและผลdev replayที่pinตรงกันแบบoffline โดยไม่แก้runtime/กราฟ และไม่เรียกบริการภายนอก:

```sh
python3 graph/evaluation/connectivity.py \
  --export graph/expansions/batches/<batch_id>/graph.json \
  --replay graph/expansions/audits/<retrieval-run>/results.json \
  --output graph/expansions/audits/<retrieval-run>/connectivity.json
```

ผล4พ.ย.2026: missinggold24occurrences =นอกseedversion9 +อยู่versionเดียวแต่ไม่มีcurrentpath13 +มีpathแต่limitตัด2. แม้oracleเลือกได้ถูกจากcurrentpaths recallเพดาน73.38% (ไม่ใช่retrievalscoreจริง) จึงไม่ควรคาดว่าปรับลำดับอย่างเดียวจะทันVector8ที่81.26%. Same-name/scope splitเป็นhintต้องตรวจ ไม่ใช่mergeapproval. รายงานอ่านง่าย: `graph/expansions/audits/20261104-retrieval-dev/CONNECTIVITY.md`; JSONล่าสุด `connectivity_checked.json`.

## ทดลองทางเข้าค้น Entity/Fact โดยตรง

`direct_search.py` เป็นoffline experimentแยกจากruntime: charTF-IDF3–5gramsค้นFact+ABOUTsubjects แล้วคืนSUPPORTED_BY chunks. ไม่ใช้LLM/embeddingAPI/reranker/merge; ไม่เลือกgoldหรือปรับเฉพาะquestionIDs. เก็บVector4เดิมแล้วเพิ่มไม่เกิน4 และมีlexicalchunksearchแบบเดียวกันเป็นcontrol. ใช้optional `requirements.txt` ในโฟลเดอร์นี้เพิ่มจากbackend dependencies (รอบนี้ใช้scikit-learn1.8.0ที่ติดตั้งอยู่แล้ว ไม่ติดตั้งแพ็กเกจเพิ่ม).

```sh
python3 graph/evaluation/direct_search.py \
  --export graph/expansions/batches/<batch_id>/graph.json \
  --baseline /absolute/path/to/friends/eval_runs/base/rag_outputs.jsonl \
  --output graph/expansions/audits/<new-experiment-name>
```

รอบแรก4พ.ย.2026 dev34ข้อ: Entity/Factrecall76.26% เทียบกราฟเดิม71.84%, lexicalchunk78.19%, Vector8 81.26%. ยังไม่แสดงประโยชน์เหนือtextretrievalcontrol ไม่เอาเข้าruntime/เปิดHybrid. ไม่มีการจูนหลังเห็นผล; ไม่ใช้test76ข้อ. รายงานในเครื่อง `graph/expansions/audits/20261104-direct-entry-dev/ANALYSIS.md`, ตาราง `RESULTS.md`, traces/pins `results.json`. งบสูงสุด8chunksไม่ใช่tokensเท่ากัน และไม่ใช่semanticembedding/answer-quality/CPEeval.
