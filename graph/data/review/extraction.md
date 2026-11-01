# ผลสกัดกราฟทดลอง 24 primary chunks

[กลับหน้าหลัก](../README.md) · [รายละเอียด](../details/extraction.md)

สถานะ: ทดลองเท่านั้น ทุก node ยัง PENDING และปิด retrieval. สคริปต์สกัดนี้ไม่เขียน Neo4j/Chroma.

Source review: 24/24 chunks; การแก้ baseline 9 จุดอยู่ `../inputs/smoke_review.json` และการแก้ pilot เพิ่ม 38 จุดอยู่ `../inputs/pilot_review.json` (ถ้ามี). ไม่แก้ raw response หรืออนุมัตินโยบาย.

Focus ของงานใหม่ใช้เฉพาะข้อความคำถาม development ไม่ส่งคำตอบ/gold; จึงเป็น targeted pilot ไม่ใช่ independent evaluation.

24/24 หมายถึงทำงานสกัดและทวนครบ ไม่ใช่สกัดครบทุก Fact; p06 ยังเป็น partial extraction ไม่มี Offering ที่ผูกทุน แทนการใช้ชื่อทุนที่โมเดลเดาจากชื่อไฟล์.

เฉพาะ baseline 5 chunks นำ response เดิมมาตรวจใหม่กับ schema pilot v1 ไม่ใช่คะแนนโมเดลรอบใหม่; งาน pilot เพิ่มใช้ response ของตนเอง.
Snapshot ต้นทาง `d24f788d4f0e0b25663d3dc4810c9758c2efa4ef9bc6d2e891a7b99728e71548` → snapshot ปัจจุบัน `397b7ddf339f52e5604a386e096e0628e6931cb4c46e45f508b7c64b2b3e71da`.
ตรวจแล้วว่า source/pilot/คำถามไม่เปลี่ยน เพิ่มได้เฉพาะ properties และลด aliases; raw records, schema_hash และบันทึก AI review เดิมยังคงต้นฉบับ.

| Chunk | Entity | Offering | Fact | ไม่ผ่านตรวจ | จุดไม่แน่ใจ | ทวนต้นทาง |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [p01](../details/extraction.md#p01) | 2 | 1 | 2 | 0 | 2 | AI ทวนแล้ว |
| [p02](../details/extraction.md#p02) | 1 | 1 | 1 | 0 | 0 | AI ทวนแล้ว |
| [p03](../details/extraction.md#p03) | 3 | 1 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p04](../details/extraction.md#p04) | 3 | 1 | 2 | 0 | 3 | AI ทวนแล้ว |
| [p05](../details/extraction.md#p05) | 3 | 1 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p06](../details/extraction.md#p06) | 1 | 0 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p07](../details/extraction.md#p07) | 1 | 1 | 2 | 0 | 3 | AI ทวนแล้ว |
| [p08](../details/extraction.md#p08) | 2 | 1 | 2 | 0 | 3 | AI ทวนแล้ว |
| [p09](../details/extraction.md#p09) | 2 | 0 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p10](../details/extraction.md#p10) | 2 | 0 | 1 | 0 | 3 | AI ทวนแล้ว |
| [p11](../details/extraction.md#p11) | 2 | 0 | 3 | 0 | 3 | AI ทวนแล้ว |
| [p12](../details/extraction.md#p12) | 1 | 0 | 2 | 0 | 1 | AI ทวนแล้ว |
| [p13](../details/extraction.md#p13) | 3 | 0 | 1 | 0 | 0 | AI ทวนแล้ว |
| [p14](../details/extraction.md#p14) | 2 | 0 | 1 | 0 | 0 | AI ทวนแล้ว |
| [p15](../details/extraction.md#p15) | 2 | 0 | 2 | 0 | 1 | AI ทวนแล้ว |
| [p16](../details/extraction.md#p16) | 1 | 0 | 2 | 0 | 3 | AI ทวนแล้ว |
| [p17](../details/extraction.md#p17) | 1 | 0 | 2 | 0 | 4 | AI ทวนแล้ว |
| [p18](../details/extraction.md#p18) | 1 | 0 | 2 | 0 | 2 | AI ทวนแล้ว |
| [p19](../details/extraction.md#p19) | 2 | 0 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p20](../details/extraction.md#p20) | 2 | 0 | 1 | 0 | 2 | AI ทวนแล้ว |
| [p21](../details/extraction.md#p21) | 3 | 0 | 2 | 0 | 3 | AI ทวนแล้ว |
| [p22](../details/extraction.md#p22) | 1 | 0 | 2 | 0 | 2 | AI ทวนแล้ว |
| [p23](../details/extraction.md#p23) | 3 | 0 | 3 | 0 | 2 | AI ทวนแล้ว |
| [p25](../details/extraction.md#p25) | 2 | 0 | 2 | 0 | 1 | AI ทวนแล้ว |

## ตัวอย่าง Fact ที่ผ่านตัวตรวจ

| Chunk | Predicate | ข้อความเดิม |
| --- | --- | --- |
| p01 | scholarship_types_count | จำนวนทุนการศึกษาเพชรพระจอมเกล้า ระดับปริญญาตรี แบ่งเป็น 2 ประเภท |
| p01 | track_quota_total | 1. ทุนส่งเสริมความสามารถด้านวิชาการดีเด่น จำนวน 15 ทุน รายละเอียดดังนี้ |
| p02 | จำนวนทุนส่งเสริมความสามารถเฉพาะด้าน | 2. ทุนส่งเสริมความสามารถเฉพาะด้าน จำนวน 20 ทุน (รวมทุกคณะ) รายละเอียดดังนี้ |
| p03 | วุฒิการศึกษาที่รับ | \| คุณสมบัติเบื้องต้น/เกณฑ์การรับสมัคร สาขาวิชา \| วุฒิการศึกษาที่รับ \| \| :--- \| :--- \| \| คณิตศาสตร์ \| ม.6 \| |
| p04 | GPAX ขั้นต่ำ | \| GPAX \| 3.60 \| - \| - \| |
| p04 | GPA คณิตศาสตร์ ขั้นต่ำ | \| GPA คณิตศาสตร์ \| 3.00 \| - \| - \| |
| p05 | minimum_gpa_foreign_language | \| GPA ภาษาต่างประเทศ \| 2.75 \| - \| - \| |
| p06 | GPAX ขั้นต่ำ | \| รายการ \| เกณฑ์การรับสมัคร/เกณฑ์การเรียกสอบคัดเลือก \| \| เกณฑ์การรับเข้าศึกษา \| \| \| เกรดเฉลี่ย/คะแนนขั้นต่ำ \| ค่าน้ำหนัก (%) \| ค่าน้ำหนัก (%) \| \| GPAX \| 3.50 \| - \| - \| |
| p07 | academic_year | เรื่อง ทุนการศึกษาเพชรพระจอมเกล้า ระดับปริญญาตรี ประจำปีการศึกษา 2568 |
| p07 | degree | ระดับปริญญาตรี ประจำปีการศึกษา 2568 |
| p08 | scholarship_count_cap | เสนอชื่อผ่านจาก ภาควิชา และคณะ ตามจำนวนทุนการศึกษาไม่เกิน 15 ทุน |
| p08 | reallocation_rule_total_cap | ผู้ให้ทุนขอสงวนสิทธิพิจารณาเกลี่ยจำนวนทุนการศึกษาเพิ่มให้แต่ละคณะหรือไม่ก็ได้ตามความเหมาะสม แต่รวมทุกคณะแล้วไม่เกิน 15 ทุน |
| p09 | ค่าใช้จ่ายตลอดหลักสูตรโดยประมาณ | \| วิศวกรรมเคมี (แผนการเรียน : ไทย) \| วศ.บ. \| 4 \| 147 \| 18 \| 650 \| 14,500 \| 26,200 \| 211,550 \| |
| p10 | ค่าใช้จ่ายตลอดหลักสูตรโดยประมาณ | \| สาขาวิชา \| ปริญญา \| จำนวนปีที่ศึกษา \| จำนวนหน่วยกิตตลอดหลักสูตร \| จำนวนหน่วยกิตที่ต้องลงเรียนในภาคการศึกษาที่ 1 \| ค่าหน่วยกิต /หน่วย \| ค่าบำรุงการศึกษา /ภาคการศึกษา \| ค่ายืนยันสิทธิการเข้าศึกษา * \| ค่าใช้จ่ายตลอดหลักสูตรโดยประมาณ \| \| :--- \| :---: \| :---: \| :---: \| :---: \| :---: \| :---: \| :---: \| :---: \| \| วิศวกรรมคอมพิวเตอร์ (หลักสูตรนานาชาติ) \| วศ.บ. \| 4 \| 138 \| 17 \| - \| เหมาจ่าย 70,000/ภาคการศึกษา \| 560,000 \| \| วิทยาศาสตร์ข้อมูลสุขภาพ (หลักสูตรร่วมระหว่างวิทยาลัยวิทยาศาสตร์การแพทย์เจ้าฟ้าจุฬาภรณ์ราชวิทยาลัยจุฬาภรณ์และ มจธ.) \| วท.บ. \| 4 \| 129 \| 17 \| - \| เหมาจ่าย 56,000/ภาคการศึกษา \| 448,000 \| \| วิศวกรรมสิ่งแวดล้อม (แผนการเรียน : ไทย) \| วศ.บ. \| 4 \| 144 \| 19 \| 650 \| 14,500 \| 26,850 \| 209,600 \| |
| p11 | ค่าใช้จ่ายตลอดหลักสูตรโดยประมาณ | \| วิศวกรรมเครื่องกล \| วศ.บ. \| 4 \| 145 \| 22 \| 650 \| 14,500 \| 28,800 \| 210,250 \| |
| p11 | คณะ | • คณะวิศวกรรมศาสตร์ |
| p11 | แหล่งข้อมูลระบุข้อมูล ณ วันที่ | ข้อมูลอาจมีการเปลี่ยนแปลงตามประกาศของมหาวิทยาลัย : ข้อมูล ณ วันที่ 12 มีนาคม 2569 |
| p12 | ค่าใช้จ่ายตลอดหลักสูตรโดยประมาณ | \| วิศวกรรมไฟฟ้า \| วศ.บ. \| 4 \| 147 \| 20 \| 650 \| 14,500 \| 27,500 \| 211,550 \| |
| p12 | ข้อมูลอาจมีการเปลี่ยนแปลงตามประกาศของมหาวิทยาลัย | ข้อมูลอาจมีการเปลี่ยนแปลงตามประกาศของมหาวิทยาลัย : ข้อมูล ณ วันที่ 12 มีนาคม 2569 |
| p13 | excluded_student_group | เพื่อให้การบริหารงานด้านวิชาการดำเนินไปด้วยความเรียบร้อย และสอดคล้องกับระเบียบมหาวิทยาลัยฯ ว่าด้วยการศึกษาของมหาวิทยาลัย ข้อบังคับ ประกาศ และแนวปฏิบัติอื่นๆ ที่เกี่ยวข้อง สำหรับนักศึกษาระดับปริญญาตรี และระดับบัณฑิตศึกษา (ยกเว้น ระดับบัณฑิตศึกษา คณะเทคโนโลยีสารสนเทศ) จึงได้จัดทำปฏิทินการศึกษา มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ประจำปีการศึกษา 2569 ไว้ดังต่อไปนี้ |
| p14 | first_submission_day | จ.15 มิ.ย. 2569 \| วันแรกของการยื่นคำร้องขอคืนสภาพการเป็นนักศึกษาเพื่อขออนุมัติจากคณะ |
| p15 | registration_period | \| จ.20 - พ.22 ก.ค. 2569 \| วันลงทะเบียนเรียนของนักศึกษาใหม่ ระดับปริญญาตรี (รหัส 69...) \| |
| p15 | transfer_credit_request_deadline_before_registration | \| ศ.10 ก.ค. 2569 \| วันสุดท้ายของการยื่นคำร้องขอเทียบโอนรายวิชา/เทียบโอนหน่วยกิตที่เรียนสะสมล่วงหน้า/เทียบความรู้ทักษะ เพื่อยกเว้นการลงทะเบียนเรียน (ก่อนลงทะเบียนเรียน) \| |
| p16 | วันสุดท้ายของการชำระเงินค่าลงทะเบียน และค่าลงทะเบียนรักษาสถานภาพการเป็นนักศึกษา | พฤ.23 ก.ค. 2569 \| วันสุดท้ายของการชำระเงินค่าลงทะเบียน และค่าลงทะเบียนรักษาสถานภาพการเป็นนักศึกษา ภาคการศึกษาที่ 1/2569 |
| p16 | วันยกเลิกรายวิชาลงทะเบียนเรียน กรณีขาดการชำระเงินค่าธรรมเนียมตามกำหนด | จ.27 ก.ค. 2569 \| วันยกเลิกรายวิชาลงทะเบียนเรียน กรณีขาดการชำระเงินค่าธรรมเนียมตามกำหนด ยกเว้น นักศึกษาที่ได้รับทุน และผ่อนผัน |
| p17 | effective_from | ข้อ 2 ข้อบังคับนี้ให้ใช้บังคับตั้งแต่วันถัดจากวันประกาศเป็นต้นไป |
| p17 | council_approval_date | ในการประชุมครั้งที่ 290 วันที่ 4 ตุลาคม 2566 |
| p18 | REVOKES | ข้อ 3 ให้ยกเลิกข้อบังคับมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี ว่าด้วย วินัยนักศึกษา พ.ศ. 2546 |
| p18 | SUPERSEDES_CONFLICTING_RULES | บรรดาความในข้อบังคับ ระเบียบ คำสั่ง หรือประกาศอื่นใดซึ่งขัดหรือแย้งกับข้อบังคับนี้ ให้ใช้ข้อบังคับนี้แทน |
| p19 | academic_integrity_prohibition | ข้อ 7 นักศึกษาและผู้เรียนรู้ต้องปฏิบัติตามข้อกำหนดด้านคุณธรรม จริยธรรม และจรรยาบรรณ ไม่ทุจริตทางวิชาการ ไม่แสวงหาผลประโยชน์อันไม่ชอบธรรมด้านวิชาการโดยเคร่งครัด |
| p20 | นิยามนักศึกษาครอบคลุมผู้เรียนข้ามมหาวิทยาลัย | “นักศึกษา” หมายความว่า นักศึกษามหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี รวมถึงนักศึกษาที่เรียนข้ามมหาวิทยาลัย |
| p21 | cannot_register_without_prior_advisor_approval | Students under ‘probation’ cannot register unless receiving academic advisors’ prior approval. Academic advisors can approve or deny the registration and inform the students of their decision with additional reasons. |
| p21 | post_approval_confirmation_and_payment | After receiving academic advisors’ approval, students must log into the system to confirm their registrations and pay the registration fee via the banking system to complete the registration process. |
| p22 | selected_by_undergraduate_students | For undergraduate students, click on Information System “New ACIS”. |
| p22 | system_login_requires | From the Login page, enter User name and Password, and then click “Enter the System” as shown below. |
| p23 | registration_menu_path | Choose the menu: Course Registration > Registration |
| p23 | section_selection_when_group_not_fixed | For unfixed section/group courses, the system will show “Section Selection”, and students can choose the section themselves. |
| p23 | group_selection_procedure | From figure 3, choose the course to register, and then click “Section Selection”. The system will show a pop-up screen as in figure 4. |
| p25 | email | E-mail : regist@kmutt.ac.th |
| p25 | phone | – ลงทะเบียนเรียน / ตารางเรียน-ตารางสอบ |

Graph export: 134 nodes / 231 edges · labels: {'SourceDocument': 8, 'DocumentVersion': 8, 'Chunk': 26, 'Entity': 45, 'Offering': 7, 'Fact': 40}

ผ่านตัวตรวจหมายถึงโครงสร้าง/ชนิดข้อมูล/quote/ตัวเลข/refs เท่านั้น ไม่ใช่การอนุมัติความหมายหรือความครบของกราฟ.
ชุดนี้เป็น targeted pilot ไม่ใช่คะแนน retrieval หรือ entity/relation recall; ยังไม่ได้ทดสอบแพ็กเกจ neo4j-graphrag.
มีผลบันทึกทดสอบ Neo4j ที่ตรงกราฟชุดนี้แล้ว ดู [ผลโหลด](../results/neo4j.json); ไม่ใช่การเปิด retrieval หรือ live health check.
ตัวตน semantic ยังแยกตาม version และ scope; ยังไม่เปิด alias/global merge จึงต้องตรวจชื่อซ้ำก่อนขยายทั้งคลัง.

## รันซ้ำ

```sh
python3 graph/build/extract.py --offline
```

`--extract` ใช้ cache และขอโมเดลแก้ผลที่ไม่ผ่านได้อีก 1 ครั้งต่อ chunk; `--offline` ตรวจผลรันที่บันทึกไว้กับ snapshot เดิมโดยไม่เรียก API.
การแก้หลังทวนผูกกับ snapshot และ response key; ถ้าข้อมูล/ผลโมเดลเปลี่ยนต้องทวนใหม่ ไม่ยกการแก้เดิมไปใช้เงียบ ๆ.

ไฟล์ใหญ่แยกที่ `../results/extraction.json`, `../results/graph.json`; raw response อยู่ `../cache/` ไม่ต้องอ่านทั้งหมด.
