# ข้อมูลสำหรับสร้างกราฟ

อ่าน [คู่มือและคำสั่ง](../README.md) ก่อน. เก็บเฉพาะ frozen inputs, ผลสกัดที่ใช้ export และ provenance ที่จำเป็น ส่วนประวัติทดลองอยู่ใน archive ที่ Git ignore

| ไฟล์ | ใช้ทำอะไร |
| --- | --- |
| inputs/schema.json | schema modsa-pilot-v1 ที่ใช้ validate/export จริง |
| inputs/aliases.json | ชื่อเรียกพร้อมหลักฐาน ไม่ใช่ global merge อัตโนมัติ |
| inputs/pilot.json | ระบุ source/chunk ต้นทางที่จะสร้างกราฟ |
| inputs/questions.json | focus และ snapshot ของตัวสกัด pilot เดิม ยังตัดออกไม่ได้โดยไม่เปลี่ยน workflow |
| inputs/smoke_review.json, pilot_review.json | การแก้/ตรวจผลสกัดที่ผูก snapshot และ response |
| results/bundle.json | manifest และ hash สำหรับตรวจว่าข้อมูลไม่เปลี่ยน |
| results/extraction.json | ผล LLM เดิม/ผล validation/provenance ใช้ replay โดยไม่เรียก API |
| results/graph.json | export กราฟ134nodes/231edges พร้อมหลักฐาน |
| results/contracts.json | ผลตรวจ data contract ทั้ง71ไฟล์/1233chunks |
| results/neo4j.json | ผลโหลด staging เดิม ไม่ใช่สถานะ DB สดหรือการอนุมัติ production |

UNKNOWN/PENDING ยังคงเดิม ไม่เปลี่ยนเป็น ACTIVE/VERIFIED จากการจัดไฟล์

inventory ใน bundle คือข้อมูล ณ frozen pilot baseline เพื่อรักษา snapshot/review เดิม ไม่ใช่จำนวนเอกสารสดทั้งคลัง. จำนวนปัจจุบันตรวจจาก contracts.json; เพิ่มเอกสารที่ไม่เกี่ยวกับpilotไม่เปลี่ยนidentity แต่แก้เอกสารที่pilotใช้อยู่ยังต้องrevalidate
