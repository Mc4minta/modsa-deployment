import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"graph/build"))
import expand
import extract
from source_evidence import anchor_payload, catalog, exception_errors, layout_view, materialize, numeric_view, segments, source_match


class SourceEvidenceTests(unittest.TestCase):
    def test_numeric_rendering_preserves_columns_but_never_html_attributes(self):
        text='<table width="100%"><tr><th>รายการ</th><th>ขั้นต่ำ</th></tr>\n<tr>\n<td>GPAX</td>\n<td style="padding: 10px">3.60</td>\n</tr></table>'
        view,ambiguous=numeric_view(text)
        self.assertFalse(ambiguous)
        self.assertEqual(view,'|รายการ|ขั้นต่ำ|\n|GPAX|3.60|')
        self.assertNotIn('10',view)
        self.assertNotIn('>',view)
        self.assertTrue(numeric_view(text.replace('<th>รายการ','<th colspan="2">รายการ'))[1])
        self.assertTrue(numeric_view('<table><tr><td>3')[1])
        self.assertEqual(numeric_view('GPA >= 3.0 และ < 4.0')[0],'GPA >= 3.0 และ < 4.0')

    def test_quantity_qualifiers_have_evidenced_bounds_not_default_equal(self):
        cases=[('ไม่ต่ำกว่า 3.25',3.25,'GTE'),('not exceed 20 MB',20,'LTE'),
               ('not\nexceeding 7 days',7,'LTE'),('A maximum of 40000 Baht',40000,'LTE'),
               ('maximum duration of 7 days',7,'LTE'),('capped at 65000 Baht',65000,'LTE'),
               ('ขั้นต่ำร้อยละ 50',50,'GTE'),('ไม่น้อยกว่าร้อยละ 80',80,'GTE'),
               ('ไม่เกินเดือนละ 2000 ยูโร',2000,'LTE')]
        for text,value,operator in cases:
            with self.subTest(text=text):
                self.primary['content']='การลงทะเบียน '+text
                record=self.record();fact=record['extraction']['facts'][0]
                fact.update(value_number=value,operator=operator)
                self.assertFalse(expand.stage(self.primary,[],record,self.schema)['rejected'])
                fact['operator']='EQ'
                self.assertIn('comparator_loses_bound',str(expand.stage(self.primary,[],record,self.schema)['rejected']))

    def test_html_table_header_and_br_are_not_greater_less_than(self):
        self.primary['content']='<table><tr><th>รายการ</th><th>ขั้นต่ำ</th></tr><tr><td>การลงทะเบียน</td><td>3.6</td></tr></table>'
        record=self.record();fact=record['extraction']['facts'][0]
        fact.update(value_number=3.6,operator='GTE')
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)['rejected'])
        fact['operator']='EQ'
        self.assertIn('comparator_loses_bound',str(expand.stage(self.primary,[],record,self.schema)['rejected']))
        self.primary['content']='| การลงทะเบียน | A maximum of 40000 Baht |'
        record=self.record();fact=record['extraction']['facts'][0]
        fact.update(value_number=40000,operator='LTE',unit='Baht')
        fact['evidence'].append({'chunk_id':'p','quote':self.primary['content']})
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)['rejected'])

    def test_merged_html_columns_and_unbound_percentages_fail_closed(self):
        self.primary['content']='<table><tr><td colspan="2">การลงทะเบียน ขั้นต่ำ</td></tr><tr><td>3.6</td><td>100</td></tr></table>'
        record=self.record();record['extraction']['facts'][0].update(value_number=3.6,operator='GTE')
        self.assertIn('unsupported_comparator',str(expand.stage(self.primary,[],record,self.schema)['rejected']))
        self.primary['content']='<table><tr><td colspan="2">การลงทะเบียน not exceed 20 MB</td></tr></table>'
        record=self.record();record['extraction']['facts'][0].update(value_number=20,operator='LTE',unit='MB')
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)['rejected'])
        self.primary['content']='การลงทะเบียน 50 คะแนน และอีกกิจกรรม ขั้นต่ำร้อยละ 80'
        record=self.record();record['extraction']['facts'][0].update(value_number=50,operator='GTE')
        self.assertIn('unsupported_comparator',str(expand.stage(self.primary,[],record,self.schema)['rejected']))

    def test_a_minimum_is_not_a_degenerate_bounded_range(self):
        self.primary['content']='การลงทะเบียน อย่างน้อย 5 ครั้ง'
        record=self.record();record['extraction']['facts'][0].update(operator='BETWEEN',
            value_lower=5,value_upper=5,lower_inclusive=True,upper_inclusive=None)
        self.assertIn('unsupported_range_or_inclusivity',str(expand.stage(self.primary,[],record,self.schema)['rejected']))

    def setUp(self):
        self.primary = {"chunk_id":"p","pilot_id":"p","source_id":"s","version_id":"v","source_index":0,
                        "content":"การลงทะเบียน ต้องยืนยันในระบบ"}
        self.schema = expand.expansion_schema(expand.read(expand.DATA/"inputs/schema.json"))

    def record(self, raw=None, quote=None):
        raw = self.primary["content"] if raw is None else raw
        evidence = [{"chunk_id":"p","quote":raw if quote is None else quote}]
        return {"extraction":{"entities":[{"ref":"e","kind":"procedure","name":"การลงทะเบียน",
                    "scope_text":"ตามข้อความ","evidence":[{"chunk_id":"p","quote":self.primary["content"]}]}],
            "offerings":[],"has_tracks":[],"unresolved":[],"facts":[{"ref":"f","subject_refs":["e"],
                "kind":"rule","predicate":"confirmation","raw_text":raw,"value_number":None,
                "value_text":None,"operator":None,"unit":None,"scope_text":"ตามข้อความ",
                "is_approximate":False,"evidence":evidence}]}}

    def wire(self):
        wire = self.record()["extraction"]
        sid = catalog(self.primary,[])[0]["span_id"]
        for item in [*wire["entities"],*wire["facts"]]:
            item["evidence"] = [{"span_id":sid}]
        wire["facts"][0].pop("raw_text")
        wire["facts"][0]["raw_span_id"] = sid
        return wire

    def test_layout_restoration_keeps_original_offsets_and_words(self):
        source = "หัวข้อ\nการลงทะเบียน<BR />ภาคเรียน  1\nท้าย"
        restored = source_match("การลงทะเบียน\nภาคเรียน 1",source)
        self.assertEqual(restored,"การลงทะเบียน<BR />ภาคเรียน  1")
        self.assertIsNone(source_match("การลงทะเบียน ภาคเรียน 2",source))
        self.assertIsNone(source_match("",source))
        view, offsets = layout_view(source)
        self.assertEqual(len(view),len(offsets))
        self.assertEqual(view,"หัวข้อ การลงทะเบียน ภาคเรียน 1 ท้าย")

    def test_paragraphs_and_table_rows_keep_boundaries_and_exact_slices(self):
        text = "หัวข้อ\nข้อความต่อเนื่อง\n\n| วัน | กิจกรรม |\n| 1 | ลดรายวิชา<br>ยกเว้น ก |\n| 2 | ชำระเงิน |\n\nท้าย\n"
        spans = segments(text)
        self.assertEqual(len(spans),5)
        self.assertEqual(spans[0][2],"หัวข้อ\nข้อความต่อเนื่อง")
        for start,end,quote in spans:
            self.assertEqual(text[start:end],quote)
        self.assertIn("ยกเว้น ก",spans[2][2])
        self.assertNotIn("ชำระเงิน",spans[2][2])

    def test_wire_schema_uses_ids_not_quotes_and_does_not_mutate_pilot(self):
        context = {**self.primary,"chunk_id":"c","content":"หลักฐานบริบท"}
        base = extract.payload_for({**self.primary,"focus":expand.FOCUS},[context],self.schema)
        before = copy.deepcopy(base)
        payload = anchor_payload(base,self.primary,[context])
        self.assertEqual(base,before)
        user = json.loads(payload["messages"][1]["content"])
        self.assertNotIn("source_chunks",user)
        self.assertNotIn("graph_schema",user)
        self.assertEqual([s["role"] for s in user["source_spans"]],["PRIMARY","CONTEXT"])
        definitions = payload["response_format"]["json_schema"]["schema"]["$defs"]
        self.assertEqual(set(definitions["Evidence"]["properties"]),{"span_id"})
        self.assertNotIn("raw_text",definitions["Fact"]["properties"])
        self.assertEqual(definitions["Fact"]["properties"]["raw_span_id"]["enum"],["c0s0"])
        self.assertIn("raw_text",base["response_format"]["json_schema"]["schema"]["$defs"]["Fact"]["properties"])

    def test_materialization_restores_entire_original_source_and_is_immutable(self):
        self.primary["content"] = "การลงทะเบียน<br>ต้องยืนยันในระบบ ยกเว้น ผู้ได้รับอนุมัติ)"
        wire = self.wire();before = copy.deepcopy(wire)
        wire["entities"][0]["name"] = "การลงทะเบียน ต้องยืนยันในระบบ"
        before = copy.deepcopy(wire)
        result = materialize(wire,self.primary,[])
        self.assertEqual(wire,before)
        self.assertEqual(result["facts"][0]["raw_text"],self.primary["content"])
        self.assertEqual(result["entities"][0]["name"],"การลงทะเบียน<br>ต้องยืนยันในระบบ")
        self.assertEqual(result["facts"][0]["evidence"][0]["quote"],self.primary["content"])
        self.assertFalse(expand.stage(self.primary,[],{"extraction":result},self.schema)["rejected"])

    def test_invalid_ids_context_facts_and_free_quotes_fail_closed(self):
        context = {**self.primary,"chunk_id":"c","content":"บริบท"}
        for variant in ("unknown","context","not_in_evidence","free_quote","raw_text"):
            with self.subTest(variant=variant):
                wire = self.wire()
                if variant=="unknown":wire["entities"][0]["evidence"]=[{"span_id":"invented"}]
                elif variant=="context":
                    wire["facts"][0]["raw_span_id"]="c1s0"
                    wire["facts"][0]["evidence"]=[{"span_id":"c1s0"}]
                elif variant=="not_in_evidence":wire["facts"][0]["evidence"]=[{"span_id":"c1s0"}]
                elif variant=="free_quote":wire["entities"][0]["evidence"][0]["quote"]="invented"
                else:wire["facts"][0]["raw_text"]="invented"
                with self.assertRaises(ValueError):materialize(wire,self.primary,[context])

    def test_malformed_source_selection_types_fail_closed(self):
        for bad in ([],None,{"entities":None},{"entities":[None]},
                    {"entities":[{"evidence":[{"span_id":[]}]}]}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                materialize(bad,self.primary,[])

    def test_html_line_breaks_are_audited_but_word_changes_are_rejected(self):
        self.primary["content"] = "การลงทะเบียน<br>ต้องยืนยันในระบบ"
        record = self.record(raw="การลงทะเบียน\nต้องยืนยันในระบบ")
        record["extraction"]["entities"][0]["name"]="การลงทะเบียน ต้องยืนยันในระบบ"
        self.assertTrue(extract.stage(self.primary,[],record,self.schema)["rejected"])
        result = expand.stage(self.primary,[],record,self.schema)
        self.assertFalse(result["rejected"])
        self.assertTrue(result["repairs"])
        record["extraction"]["facts"][0]["raw_text"]="การลงทะเบียน ต้องถอนในระบบ"
        self.assertTrue(expand.stage(self.primary,[],record,self.schema)["rejected"])

    def test_exception_check_ignores_closing_punctuation_not_missing_words(self):
        content = "| การลงทะเบียน ยกเว้น ผู้ได้รับอนุมัติ) |"
        self.assertFalse(exception_errors(content,"ยกเว้น ผู้ได้รับอนุมัติ"))
        self.assertTrue(exception_errors(content,"ยกเว้น ผู้ได้รับ"))
        self.assertTrue(exception_errors(content,"การลงทะเบียน"))

    def test_missing_exception_is_rejected_even_when_model_labels_it_fact(self):
        self.primary["content"]="การลงทะเบียน ได้รับเงินคืนร้อยละ 80 ยกเว้น หลักสูตรเหมาจ่าย"
        for kind in ("fact","rule"):
            with self.subTest(kind=kind):
                record=self.record(raw="ได้รับเงินคืนร้อยละ 80")
                fact=record["extraction"]["facts"][0]
                fact.update(kind=kind,value_number=80,operator="EQ",unit="ร้อยละ")
                rejected=expand.stage(self.primary,[],record,self.schema)["rejected"]
                self.assertIn("truncated_source_exception",str(rejected))

    def test_other_table_rows_do_not_supply_unrelated_exceptions(self):
        content="| การลงทะเบียน ต้องยืนยันในระบบ |\n| อีกกิจกรรม ยกเว้น ผู้ได้รับอนุมัติ |"
        self.assertFalse(exception_errors(content,"การลงทะเบียน ต้องยืนยันในระบบ"))

    def test_real_subject_errors_are_not_silently_dropped(self):
        wire=self.wire();wire["facts"][0]["subject_refs"]=["invented-entity"]
        record={"extraction":materialize(wire,self.primary,[])}
        result=expand.stage(self.primary,[],record,self.schema)
        self.assertIn("invalid_subject_refs",str(result["rejected"]))

    def test_thai_identity_spacing_restores_only_original_characters(self):
        self.assertEqual(source_match("การศึกษาระดับบัณฑิตศึกษา","การศึกษา\nระดับบัณฑิตศึกษา",thai_spacing=True),
                         "การศึกษา\nระดับบัณฑิตศึกษา")
        self.assertIsNone(source_match("notable","not able",thai_spacing=True))
        self.assertIsNone(source_match("10","1 0",thai_spacing=True))
        self.assertIsNone(source_match("การศึกษาระดับปริญญาตรี","การศึกษา\nระดับบัณฑิตศึกษา",thai_spacing=True))

    def test_unit_scoping_disambiguates_deadline_from_same_number_in_dates(self):
        self.primary["content"]="| อ.1 ก.ย. 2569 | การลงทะเบียน ภาคการศึกษาที่ 1/2569 ชำระเงิน ไม่เกิน 1 วัน |"
        record=self.record();fact=record["extraction"]["facts"][0]
        fact.update(value_number=1,operator="LTE",unit="วัน")
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])
        fact["operator"]="EQ"
        self.assertTrue(expand.stage(self.primary,[],record,self.schema)["rejected"])

    def test_thai_suffix_lower_bound_is_preserved_not_assumed_exact(self):
        self.primary["content"]="การลงทะเบียน ต้องมี GPA 3.0 ขึ้นไป"
        record=self.record();fact=record["extraction"]["facts"][0]
        fact.update(value_number=3.0,operator="GTE",unit="GPA")
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])
        fact["operator"]="EQ"
        self.assertTrue(expand.stage(self.primary,[],record,self.schema)["rejected"])
        self.primary["content"]="การลงทะเบียน ไม่เกิน 3.0 ขึ้นไป"
        contradictory=self.record();contradictory["extraction"]["facts"][0].update(value_number=3.0,operator="GTE")
        self.assertTrue(expand.stage(self.primary,[],contradictory,self.schema)["rejected"])

    def test_table_approximation_applies_only_to_the_target_column(self):
        header="| หลักสูตร | ค่ายืนยัน | ค่าใช้จ่ายโดยประมาณ |"
        row="| การลงทะเบียน | 100 | 900 |"
        self.primary["content"]=header+"\n"+row
        record=self.record(raw=row)
        fact=record["extraction"]["facts"][0]
        fact["evidence"].append({"chunk_id":"p","quote":header})
        fact.update(value_number=100,operator="EQ",is_approximate=False)
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])
        fact["value_number"]=900
        self.assertIn("lost_approximation",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))
        fact["is_approximate"]=True
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])

    def test_source_selection_cannot_make_an_unsupported_number_valid(self):
        self.primary["content"]="การลงทะเบียน มีค่าปรับวันละ 50 บาท"
        wire=self.wire()
        wire["facts"][0].update(value_number=80,operator="EQ",unit="บาท")
        result=expand.stage(self.primary,[],{"extraction":materialize(wire,self.primary,[])},self.schema)
        self.assertIn("unsupported_number",str(result["rejected"]))

    def test_deadline_comparators_survive_line_breaks_without_losing_bounds(self):
        for text in ("การลงทะเบียน ภายใน 30 วัน", "การลงทะเบียน ไม่เกิน\n30 วัน",
                     "การลงทะเบียน within 30 วัน", "การลงทะเบียน ไม่เกิน<br>30 วัน"):
            with self.subTest(text=text):
                self.primary["content"]=text
                record=self.record();fact=record["extraction"]["facts"][0]
                fact.update(value_number=30,operator="LTE",unit="วัน")
                self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])
                fact["operator"]="EQ"
                self.assertTrue(expand.stage(self.primary,[],record,self.schema)["rejected"])

    def test_same_number_in_different_clauses_remains_ambiguous(self):
        self.primary["content"]="การลงทะเบียน ไม่เกิน 20 คะแนน และมากกว่า 20 คะแนนต่อปี"
        record=self.record();record["extraction"]["facts"][0].update(value_number=20,operator="LTE",unit="คะแนน")
        self.assertIn("unsupported_comparator",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))
        self.primary["content"]="การลงทะเบียน not within 20 วัน"
        record=self.record();record["extraction"]["facts"][0].update(value_number=20,operator="LTE",unit="วัน")
        self.assertIn("unsupported_comparator",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))

    def test_approximation_is_not_inherited_from_budget_or_other_quantity(self):
        for text in ("การลงทะเบียน งบประมาณสนับสนุน ไม่เกิน 30000 บาท",
                     "การลงทะเบียน จ่าย 30000 บาท หลังลงนามประมาณ 1 เดือน"):
            self.primary["content"]=text
            record=self.record();record["extraction"]["facts"][0].update(value_number=30000,operator="LTE" if "ไม่เกิน" in text else "EQ",unit="บาท")
            self.assertNotIn("lost_approximation",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))
        for text in ("การลงทะเบียน ประมาณ 30000 บาท", "การลงทะเบียน 30000 บาทโดยประมาณ"):
            self.primary["content"]=text
            record=self.record();record["extraction"]["facts"][0].update(value_number=30000,operator="EQ",unit="บาท")
            self.assertIn("lost_approximation",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))

    def test_redundant_scalar_flags_are_audited_not_contradictory_bounds(self):
        self.primary["content"]="การลงทะเบียน อย่างน้อย 3 หน่วยกิต"
        record=self.record();fact=record["extraction"]["facts"][0]
        fact.update(value_number=3,operator="GTE",unit="หน่วยกิต",lower_inclusive=True)
        before=copy.deepcopy(record)
        result=expand.stage(self.primary,[],record,self.schema)
        self.assertFalse(result["rejected"])
        self.assertTrue(any(r["method"]=="redundant-scalar-bound-v1" for r in result["repairs"]))
        self.assertEqual(record,before)
        for changes in ({"lower_inclusive":False},{"value_lower":2},{"upper_inclusive":True}):
            invalid=copy.deepcopy(record);invalid["extraction"]["facts"][0].update(changes)
            self.assertIn("invalid_output_contract",str(expand.stage(self.primary,[],invalid,self.schema)["rejected"]))

    def test_offering_scope_accepts_evidenced_languages_not_update_dates(self):
        for degree in ("Ph.D.","master's degree","มหาบัณฑิต","วท.ม.","ปริญญาตรี"):
            offering=extract.Offering(ref="o",scholarship_ref="e",academic_year_be=2569,
                round="1st Intake",degree=degree,evidence=[extract.Evidence(chunk_id="p",quote=
                f"ทุน Scholarship {degree} Academic year 2026 1st Intake")])
            for field in ("degree","academic_year_be","round"):
                self.assertTrue(extract.supported_offering_scope(offering,field),(degree,field))
            offering.evidence[0].quote=f"ข้อมูล ณ มกราคม 2569 {degree} ภาคการศึกษาที่ 1"
            self.assertFalse(extract.supported_offering_scope(offering,"academic_year_be"))
            self.assertFalse(extract.supported_offering_scope(offering,"round"))
            offering.degree="ม.6"
            offering.evidence[0].quote="ทุน รับผู้จบ ม.6"
            self.assertFalse(extract.supported_offering_scope(offering,"degree"))

    def test_fee_cannot_masquerade_as_scholarship(self):
        self.primary["content"]="การลงทะเบียน ค่ายืนยันสิทธิการเข้าศึกษา 30000 บาท"
        record=self.record();record["extraction"]["entities"][0].update(kind="scholarship",name="ค่ายืนยันสิทธิการเข้าศึกษา")
        self.assertIn("unsupported_scholarship_identity",str(expand.stage(self.primary,[],record,self.schema)["rejected"]))
        record["extraction"]["entities"][0]["kind"]="fee"
        self.assertFalse(expand.stage(self.primary,[],record,self.schema)["rejected"])

    def test_non_numeric_contacts_urls_and_scope_keep_text_and_source_conditions(self):
        cases=[("สำนักงานทะเบียน","office","อีเมล office@example.org","office@example.org"),
               ("สำนักงานทะเบียน","office","โทรศัพท์ +66 (0)2 123 4567","+66 (0)2 123 4567"),
               ("การทำบัตร","procedure","บริการ https://example.org/card","https://example.org/card"),
               ("ปฏิทิน","policy","ใช้กับนักศึกษาทุกคน ยกเว้น กลุ่ม ก","นักศึกษาทุกคน")]
        for name,kind,text,value in cases:
            with self.subTest(kind=kind,value=value):
                self.primary["content"]=name+" "+text
                wire=self.wire()
                wire["entities"][0].update(name=name,kind=kind)
                wire["facts"][0].update(kind="fact",value_text=value,value_number=None,operator=None,unit=None)
                result=materialize(wire,self.primary,[])
                checked=expand.stage(self.primary,[],{"extraction":result},self.schema)
                self.assertFalse(checked["rejected"])
                self.assertEqual(checked["facts"][0]["value_text"],value)
                self.assertEqual(checked["facts"][0]["raw_text"],self.primary["content"])


if __name__=="__main__":
    unittest.main()
