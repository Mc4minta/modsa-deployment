# ผลตรวจ data contract ทั้งคลัง

[กลับคู่มือสร้างกราฟ](../../README.md)

ตรวจ 71 ไฟล์ · ผ่านโครงสร้าง 71 · 1233 chunks · ข้อผิดพลาด 0

นี่คือ sidecar ที่เพิ่มสัญญาข้อมูล ไม่เขียนทับ chunks และไม่รับรองว่านโยบายยัง ACTIVE.
SourceDocument แยกจาก DocumentVersion และ Chunk; canonical chunk_id ผูก version+ลำดับ ส่วน legacy_chunk_id คง ID ที่ Vector RAG ใช้อยู่.
ingested_at มีความละเอียดระดับวัน; legacy last_updated จาก chunk generator ถูกระบุ origin ไว้ ไม่ใช้เป็น published_at/effective_from.
source_uri ใช้ URL ที่ระบุไว้ หรือ path ของ JSON ที่เตรียมแล้ว; content_type=application/json ไม่ได้อ้างว่าเป็นชนิดไฟล์ต้นฉบับ PDF.

## Metadata ที่ยังไม่บันทึก — ไม่ใช่เงื่อนไขรอทีม Data

ตัวเลขด้านล่างตรวจ metadata ที่บันทึกไว้เท่านั้น ไม่ได้บอกว่าข้อมูลไม่มีในเอกสาร และยังไม่ได้สกัดวันที่/สถานะจากเนื้อหาครบทั้งคลัง.
ให้ดึงข้อมูลที่ระบุชัดจากเอกสารพร้อม chunk/page/quote; ไม่พบหรือขัดกันคง null/UNKNOWN และตรวจเฉพาะจุด โดยเดินหน้ากราฟทดลองได้.
owner_verification เป็นชื่อรายการ audit เดิม หมายถึงยังไม่มีการรับรองที่บันทึกไว้ ไม่ใช่ field บังคับหรือเงื่อนไขหยุด pilot; ไม่เปลี่ยน VERIFIED เพียงเพราะสกัดจากเอกสาร.
ไม่อนุมาน ACTIVE จากวันประกาศ และไม่ใช้ปีการศึกษา วัน ingest หรือชื่อไฟล์แทนวันประกาศ/วันมีผล.

| Field / รายการ audit | เอกสารที่ยังไม่บันทึก |
| --- | ---: |
| document_status | 71 |
| effective_from | 71 |
| official_source_url | 58 |
| owner_verification | 71 |
| published_at | 71 |

## แยกตามเอกสาร

| เอกสาร | ยังไม่บันทึก / รายการ audit | Chunks ไม่ทราบหน้า |
| --- | --- | ---: |
| AcademicCalendar2026-2569TH2 | published_at, effective_from, document_status, owner_verification | 0 |
| discipline2566 | published_at, effective_from, document_status, owner_verification | 0 |
| rule_exam2560 | published_at, effective_from, document_status, owner_verification | 0 |
| ระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการศึกษาระดับบัณฑิตศึกษา | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| 20Mar69-ค่าใช้จ่ายตลอดหลักสูตรปตรี-69 | published_at, effective_from, document_status, owner_verification | 0 |
| ขั้นตอนการพิมพ์ใบเสร็จรับเงินค่าลงทะเบียนเรียนระบบNewACIS.md | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ปริญญาเอก-ข้อมูลค่ายืนยันสิทธิ-และค่าใช้จ่ายตลอดหลักสูตร-2568 | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ปริญญาโท-ข้อมูลค่ายืนยันสิทธิ-และค่าใช้จ่ายตลอดหลักสูตร-2568 | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| MODsa-proposal_students | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| Manual-แนะนำบริการสารสนเทศ_ver2024 | published_at, effective_from, document_status, owner_verification | 0 |
| ขั้นตอนการทำบัตรนักศึกษา | published_at, effective_from, document_status, owner_verification | 1 |
| ติดต่อสำนักงานทะเบียน | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| บัตรนักศึกษา-Digital-มจธ | published_at, effective_from, document_status, owner_verification, official_source_url | 6 |
| The_Student’s_Internet_Registration_Manual_(fixed) | published_at, effective_from, document_status, owner_verification | 0 |
| pop-up-blocker-disable | published_at, effective_from, document_status, owner_verification | 0 |
| ขั้นตอนการถอนใน_New_ACIS | published_at, effective_from, document_status, owner_verification | 0 |
| คู่มือบันทึกระเบียนประวัตินักศึกษา | published_at, effective_from, document_status, owner_verification | 0 |
| คู่มือลงทะเบียน_ผ่านระบบ_Internet_สำหรับนักศึกษา | published_at, effective_from, document_status, owner_verification | 0 |
| วิธียื่นคำขอลาพักการศึกษา_การ_Drop_(fixed) | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| KMUTT-Scholarship-2558 | published_at, effective_from, document_status, owner_verification | 0 |
| R1-เกณฑ์การรับ-ทุนเพรชฯ-69 | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_active_recruitment_scholarship_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_axtra_star_scholarship_application_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_bank_of_thailand_scholarship_application_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_boon_rawd_student_development_scholarship_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_disabled_undergraduate_education_subsidy_application_2026_semester1_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_disaster_relief_scholarship_2025_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_exxonmobil_rattanakosin_200th_anniversary_scholarship_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_greater_mekong_subregion_graduate_scholarship_2025_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_international_scholarships_program_kisp_2024_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_jeranai_petch_scholarship_2019_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_joint_scholarship_request_form_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_mod_link_volunteer_activity_recording_manual_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_multi_intellectuals_scholarship_2024_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_paiboon_hangsapruek_emergency_scholarship_2025_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_phd_short_term_research_abroad_application_schedule_2026_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_phd_short_term_research_abroad_funding_criteria_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_phd_short_term_research_abroad_funding_criteria_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_phd_short_term_research_abroad_funding_flowchart_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_phd_short_term_research_abroad_grant_recipient_guide_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_master_scholarship_2026_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_master_scholarship_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_phd_research_scholarship_2026_en | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_phd_research_scholarship_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_undergraduate_admission_round1_criteria_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_undergraduate_scholarship_2027_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_undergraduate_scholarship_recipient_conditions_2025_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_pra_jom_klao_undergraduate_scholarship_student_guide_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_petchra_scholarship_resignation_and_repayment_request_form_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_real_applied_learning_2_student_employment_scholarship_2026_semester1_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_rukkhaphitthayaphat_master_scholarship_2023_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_saed_lueang_rueang_rung_scholarship_2024_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_saed_lueang_rueang_rung_scholarship_application_schedule_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_scholarships_for_international_students_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_shinshokai_foundation_scholarship_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_siriwiriya_scholarship_application_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_student_loan_fund_disbursement_timeline_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_student_loan_fund_education_status_reporting_guide_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_student_loan_fund_new_student_faq_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_student_loan_fund_new_student_faq_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_thaioil_scholarship_application_2026_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_thammaraksa_scholarship_2025_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| kmutt_vsf_volunteer_activity_submission_manual_th | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| กยศ68 | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| คำถามต้องการกู้ยืมเงินกยศ | published_at, effective_from, document_status, owner_verification, official_source_url | 4 |
| คู่มือนศ.ทุนเพชรพระจอมเกล้าป.ตรี | published_at, effective_from, document_status, owner_verification | 0 |
| ทุนการศึกษา_Active_Recruitment | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ทุนการศึกษาสำหรับนักศึกษาปัจจุบัน | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ทุนนักศึกษาสำหรับนักศึกษานานาชาติ | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ประกาศทุนรุกขพิทยพัฒน์-ระดับมหาบัณฑิต-2566DS | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |
| ประกาศทุนเพชรฯป.ตรี-และเงื่อนไข-68 | published_at, effective_from, document_status, owner_verification, official_source_url | 0 |

ผลละเอียด: [contracts.json](../results/contracts.json)

ยังไม่ได้ทำ workflow upsert/supersede/delete ในฐานข้อมูล และไม่ต้องรอส่งรายงานให้ทีม Data ก่อนทดลองกราฟ การขาดวันที่ไม่ถูกเติมด้วยการเดา.
