"""Synthetic extraction/evidence/numeric guards, independent of pilot files."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/build"))
from common import restore_source_whitespace
from extract import Evidence, export_graph, stage
from common import fingerprint


class GraphSmokeTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "graph/data/inputs/schema.json").read_text(encoding="utf-8"))
        self.primary = {"pilot_id": "p01", "chunk_id": "doc#0001", "source_id": "doc", "version_id": "doc@v1",
            "source_index": 0, "category": "scholarship", "page": 1, "role": "primary",
            "content": "ทุน X ระดับปริญญาตรี ปี 2569 รอบ 1 จำนวน 15 ทุน"}
        evidence = [{"chunk_id": self.primary["chunk_id"], "quote": self.primary["content"]}]
        self.record = {"extraction": {"entities": [
            {"ref": "s", "kind": "scholarship", "name": "ทุน X", "scope_text": "ปี 2569 รอบ 1", "evidence": evidence}],
            "offerings": [], "facts": [
                {"ref": "f", "subject_refs": ["s"], "kind": "fact", "predicate": "quota",
                 "raw_text": "จำนวน 15 ทุน", "value_number": 15, "value_text": None, "operator": "EQ",
                 "unit": "ทุน", "scope_text": "ปี 2569 รอบ 1", "is_approximate": False, "evidence": evidence}],
            "has_tracks": [], "unresolved": []}}

    def bundle(self, chunks):
        first = chunks[0]
        return {"snapshot_hash": "test-snapshot", "schema": self.schema, "pilot": chunks,
            "sources": [{"source_id": "doc", "source_path": "scholarship/doc.json", "title": "Test source",
                         "version_id": first["version_id"], "content_hash": "test-content-hash", "category": "scholarship",
                         "published_at": None, "effective_from": None, "document_status": "UNKNOWN",
                         "verification_status": "UNVERIFIED"}]}

    def test_valid_numeric_fact_exports_as_pending_only(self):
        result = stage(self.primary, [], self.record, self.schema)
        self.assertEqual(len(result["facts"]), 1)
        self.assertFalse(result["rejected"])
        graph = export_graph(self.bundle([self.primary]), [(self.primary, [])], {"p01": result})
        self.assertTrue(graph["nodes"])
        self.assertTrue(all(n["properties"]["review_status"] == "PENDING" for n in graph["nodes"]))
        self.assertTrue(all(n["properties"]["retrieval_enabled"] is False for n in graph["nodes"]))
        self.assertTrue(any(e["type"] == "SUPPORTED_BY" for e in graph["edges"]))

    def test_export_rejects_properties_outside_frozen_schema(self):
        result = stage(self.primary, [], self.record, self.schema)
        result["facts"][0]["invented_property"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "Undeclared node properties"):
            export_graph(self.bundle([self.primary]), [(self.primary, [])], {"p01": result})

    def test_modified_quote_is_not_evidence(self):
        record = copy.deepcopy(self.record)
        record["extraction"]["facts"][0]["evidence"][0]["quote"] = "ทุน X จำนวนไม่เกิน 15 ทุน"
        self.assertFalse(stage(self.primary, [], record, self.schema)["facts"])

    def test_only_whitespace_can_be_restored_with_audit(self):
        evidence = [Evidence(chunk_id="c", quote="Office email@example.com")]
        repairs = restore_source_whitespace(evidence, {"c": {"content": "Office\nemail@example.com"}})
        self.assertEqual(evidence[0].quote, "Office\nemail@example.com")
        self.assertEqual(len(repairs), 1)
        wrong = [Evidence(chunk_id="c", quote="Office other@example.com")]
        self.assertFalse(restore_source_whitespace(wrong, {"c": {"content": "Office\nemail@example.com"}}))

    def test_raw_text_whitespace_repair_is_audited_without_changing_model_record(self):
        primary = {**self.primary, "content": "ทุน X\nจำนวน 15 ทุน"}
        record = copy.deepcopy(self.record)
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record["extraction"]["entities"][0]["evidence"] = evidence
        fact = record["extraction"]["facts"][0]
        fact.update(raw_text="ทุน X จำนวน 15 ทุน", evidence=evidence)
        original = copy.deepcopy(record)
        result = stage(primary, [], record, self.schema)
        self.assertEqual(result["facts"][0]["raw_text"], primary["content"])
        self.assertTrue(any(r.get("field") == "raw_text" for r in result["repairs"]))
        self.assertEqual(record, original)
        fact["raw_text"] = "ทุน X จำนวน 99 ทุน"
        self.assertFalse(stage(primary, [], record, self.schema)["facts"])

    def test_numeric_strings_and_invented_numbers_are_rejected(self):
        for unsupported in ("15", 999):
            with self.subTest(value=unsupported):
                record = copy.deepcopy(self.record)
                record["extraction"]["facts"][0]["value_number"] = unsupported
                self.assertFalse(stage(self.primary, [], record, self.schema)["facts"])

    def range_record(self, text="รายได้ 6,501-12,500 บาท", **changes):
        primary = {**self.primary, "content": "ทุน X " + text}
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record = copy.deepcopy(self.record)
        record["extraction"]["entities"][0]["evidence"] = evidence
        fact = record["extraction"]["facts"][0]
        fact.update(predicate="monthly_income_range", raw_text=text, value_number=None, value_text=None,
                    operator="BETWEEN", value_lower=6501, value_upper=12500,
                    lower_inclusive=None, upper_inclusive=None, unit="THB", evidence=evidence)
        fact.update(changes)
        return primary, record

    def test_between_preserves_unknown_inclusivity_and_exports_both_bounds(self):
        primary, record = self.range_record()
        original = copy.deepcopy(record)
        result = stage(primary, [], record, self.schema)
        self.assertFalse(result["rejected"])
        self.assertEqual(record, original)
        fact = result["facts"][0]
        self.assertEqual((fact["value_lower"], fact["value_upper"]), (6501, 12500))
        self.assertIsNone(fact["lower_inclusive"])
        self.assertIsNone(fact["upper_inclusive"])
        graph = export_graph(self.bundle([primary]), [(primary, [])], {"p01": result})
        props = next(node["properties"] for node in graph["nodes"] if node["label"] == "Fact")
        self.assertEqual(props["operator"], "BETWEEN")
        self.assertEqual(props["value_upper"], 12500)
        self.assertIsNone(props["upper_inclusive"])

    def test_between_rejects_bad_bounds_and_mixed_value_representations(self):
        for changes in ({"value_lower": 15000}, {"value_lower": "6501"}, {"value_lower": True},
                        {"value_upper": float("inf")}, {"value_lower": float("nan")},
                        {"value_upper": None}, {"value_number": 6501}, {"value_text": "6,501-12,500"},
                        {"operator": "EQ"}, {"lower_inclusive": "true"}):
            with self.subTest(changes=changes):
                primary, record = self.range_record(**changes)
                self.assertFalse(stage(primary, [], record, self.schema)["facts"])

    def test_between_requires_paired_bounds_inside_primary_raw_text(self):
        for text in ("รายได้ 6,501 บาท และค่าใช้จ่าย 12,500 บาท", "รายได้ 6,501 และ 12,500 บาท",
                     "รายได้ 6,501-8,000 หรือ 9,000-12,500 บาท", "รายได้ 6,501-12,5000 บาท",
                     "รายได้ 6,501\n-12,500 บาท"):
            with self.subTest(text=text):
                primary, record = self.range_record(text)
                self.assertFalse(stage(primary, [], record, self.schema)["facts"])
        primary, record = self.range_record()
        record["extraction"]["facts"][0]["raw_text"] = "รายได้ 6,501"
        self.assertFalse(stage(primary, [], record, self.schema)["facts"])

    def test_between_does_not_infer_inclusivity_from_dash(self):
        for changes in ({"lower_inclusive": True}, {"upper_inclusive": True},
                        {"lower_inclusive": False}, {"upper_inclusive": False}):
            with self.subTest(changes=changes):
                primary, record = self.range_record(**changes)
                self.assertFalse(stage(primary, [], record, self.schema)["facts"])

    def test_between_explicit_comparators_must_match_each_endpoint(self):
        primary, record = self.range_record("รายได้มากกว่า 6,501 และไม่เกิน 12,500 บาท",
                                            lower_inclusive=False, upper_inclusive=True)
        self.assertEqual(len(stage(primary, [], record, self.schema)["facts"]), 1)
        for changes in ({"lower_inclusive": True}, {"upper_inclusive": False},
                        {"lower_inclusive": None}, {"upper_inclusive": None}):
            with self.subTest(changes=changes):
                changed = copy.deepcopy(record)
                changed["extraction"]["facts"][0].update(changes)
                self.assertFalse(stage(primary, [], changed, self.schema)["facts"])

    def test_old_scalar_fact_omits_new_range_fields_to_preserve_identity(self):
        result = stage(self.primary, [], self.record, self.schema)
        self.assertFalse({"value_lower", "value_upper", "lower_inclusive", "upper_inclusive"} & result["facts"][0].keys())

    def test_minimum_cannot_become_exact_value(self):
        primary = {**self.primary, "content": "ทุน X ปี 2569 รอบ 1 GPAX ขั้นต่ำ 3.60"}
        record = copy.deepcopy(self.record)
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record["extraction"]["entities"][0]["evidence"] = evidence
        fact = record["extraction"]["facts"][0]
        fact.update(predicate="gpax_minimum", raw_text="GPAX ขั้นต่ำ 3.60", value_number=3.6, unit=None, evidence=evidence)
        self.assertFalse(stage(primary, [], record, self.schema)["facts"])
        fact["operator"] = "GTE"
        self.assertEqual(len(stage(primary, [], record, self.schema)["facts"]), 1)

    def test_maximum_cannot_become_exact_value(self):
        primary = {**self.primary, "content": "ทุน X ปี 2569 รอบ 1 จำนวนไม่เกิน 15 ทุน"}
        record = copy.deepcopy(self.record)
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record["extraction"]["entities"][0]["evidence"] = evidence
        fact = record["extraction"]["facts"][0]
        fact.update(raw_text="จำนวนไม่เกิน 15 ทุน", evidence=evidence)
        self.assertFalse(stage(primary, [], record, self.schema)["facts"])
        fact["operator"] = "LTE"
        self.assertEqual(len(stage(primary, [], record, self.schema)["facts"]), 1)

    def test_scalar_comparators_are_bound_to_the_target_number(self):
        cases = [
            ("อย่างน้อย 9 หน่วยกิต",9,"GTE",True),
            ("ไม่น้อยกว่า 9 หน่วยกิต และไม่เกิน 22 หน่วยกิต",9,"GTE",True),
            ("ไม่น้อยกว่า 9 หน่วยกิต และไม่เกิน 22 หน่วยกิต",22,"LTE",True),
            ("จำนวน 9 หน่วยกิต",9,"GT",False),
            ("จำนวน 9 หน่วยกิต",9,"LT",False),
            ("มากกว่า 9 หน่วยกิต",9,"GT",True),
            ("น้อยกว่า 9 หน่วยกิต",9,"LT",True),
            ("greater than or equal to 9 credits",9,"GTE",True),
            ("greater than or equal to 9 credits",9,"EQ",False),
            ("อย่างน้อย 9 หน่วยกิต",9,"EQ",False),
            ("อย่างน้อย 9 หน่วยกิต",9,"LTE",False),
            ("ค่าใช้จ่าย -9 บาท",9,"EQ",False),
            ("ค่าใช้จ่าย -9 บาท",-9,"EQ",True),
        ]
        for text,number,operator,accepted in cases:
            with self.subTest(text=text,operator=operator):
                primary={**self.primary,"content":"ทุน X "+text}
                record=copy.deepcopy(self.record)
                evidence=[{"chunk_id":primary["chunk_id"],"quote":primary["content"]}]
                record["extraction"]["entities"][0]["evidence"]=evidence
                record["extraction"]["facts"][0].update(raw_text=text,value_number=number,operator=operator,evidence=evidence)
                result=stage(primary,[],record,self.schema)
                self.assertEqual(bool(result["facts"]),accepted,result["rejected"])

    def test_other_evidence_minimum_does_not_change_an_unrelated_exact_count(self):
        primary={**self.primary,"content":"ทุน X จำนวน 15 ทุน\nอย่างน้อย 9 หน่วยกิต"}
        record=copy.deepcopy(self.record)
        record["extraction"]["facts"][0]["evidence"]=[{"chunk_id":primary["chunk_id"],"quote":primary["content"]}]
        record["extraction"]["entities"][0]["evidence"]=record["extraction"]["facts"][0]["evidence"]
        self.assertFalse(stage(primary,[],record,self.schema)["rejected"])

    def test_rule_cannot_hide_exception_by_truncating_both_raw_and_quote(self):
        rule = "วันยกเลิกรายวิชาลงทะเบียนเรียน กรณีขาดการชำระเงินค่าธรรมเนียมตามกำหนด"
        complete = rule + " ยกเว้น นักศึกษาที่ได้รับทุน และผ่อนผัน"
        primary = {**self.primary, "content": "ทุน X ภาคการศึกษาที่ 1/2569\n" + complete}
        record = copy.deepcopy(self.record)
        record["extraction"]["entities"][0].update(scope_text="ภาคการศึกษาที่ 1/2569",
            evidence=[{"chunk_id": primary["chunk_id"], "quote": "ทุน X ภาคการศึกษาที่ 1/2569"}])
        fact = record["extraction"]["facts"][0]
        fact.update(kind="rule", predicate="nonpayment_cancellation", raw_text=rule, value_number=None,
            value_text=None, operator=None, unit=None, scope_text="ภาคการศึกษาที่ 1/2569",
            evidence=[{"chunk_id": primary["chunk_id"], "quote": rule}])
        self.assertFalse(stage(primary, [], record, self.schema)["facts"])
        fact.update(raw_text=complete, evidence=[{"chunk_id": primary["chunk_id"], "quote": complete}])
        self.assertEqual(len(stage(primary, [], record, self.schema)["facts"]), 1)

    def test_offering_round_requires_round_anchor_not_an_unrelated_digit(self):
        primary = {**self.primary, "content": "ทุน X ระดับปริญญาตรี รอบที่ 1 (ปีการศึกษา 2569)\nแบ่งเป็น 2 ประเภท"}
        record = copy.deepcopy(self.record)
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record["extraction"]["entities"][0]["evidence"] = evidence
        record["extraction"]["facts"] = []
        offering = {"ref": "o", "scholarship_ref": "s", "academic_year_be": 2569,
            "round": "2", "degree": "ปริญญาตรี", "evidence": evidence}
        record["extraction"]["offerings"] = [offering]
        self.assertFalse(stage(primary, [], record, self.schema)["offerings"])
        offering["round"] = "1"
        self.assertEqual(len(stage(primary, [], record, self.schema)["offerings"]), 1)

    def test_unknown_subject_does_not_create_dangling_fact(self):
        record = copy.deepcopy(self.record)
        record["extraction"]["facts"][0]["subject_refs"] = ["not-produced"]
        self.assertFalse(stage(self.primary, [], record, self.schema)["facts"])

    def test_duplicate_local_refs_are_rejected(self):
        record = copy.deepcopy(self.record)
        record["extraction"]["facts"][0]["ref"] = "s"
        result = stage(self.primary, [], record, self.schema)
        self.assertFalse(result["facts"])
        self.assertTrue(result["rejected"])

    def test_context_only_fact_cannot_pass_as_primary_extraction(self):
        context = {**self.primary, "pilot_id": "p02", "chunk_id": "doc#0002", "source_index": 1, "role": "context"}
        record = copy.deepcopy(self.record)
        record["extraction"]["facts"][0]["evidence"] = [{"chunk_id": context["chunk_id"], "quote": context["content"]}]
        self.assertFalse(stage(self.primary, [context], record, self.schema)["facts"])

    def test_study_program_track_is_not_scholarship_track(self):
        primary = {**self.primary, "content": self.primary["content"] + " ด้านวิชาการ"}
        record = copy.deepcopy(self.record)
        evidence = [{"chunk_id": primary["chunk_id"], "quote": primary["content"]}]
        record["extraction"]["entities"].append({"ref": "t", "kind": "program_track", "name": "ด้านวิชาการ",
            "scope_text": "ปี 2569 รอบ 1", "evidence": evidence})
        record["extraction"]["offerings"] = [{"ref": "o", "scholarship_ref": "s", "academic_year_be": 2569,
            "round": "1", "degree": "ปริญญาตรี", "evidence": evidence}]
        record["extraction"]["has_tracks"] = [{"offering_ref": "o", "track_ref": "t", "evidence": evidence}]
        result = stage(primary, [], record, self.schema)
        self.assertFalse(result["has_tracks"])
        self.assertTrue(result["rejected"])

    def test_chunk_identity_is_version_scoped_and_adjacency_never_skips(self):
        first = copy.deepcopy(self.primary)
        third = {**first, "pilot_id": "p03", "chunk_id": "doc#0003", "source_index": 2, "role": "context"}
        empty = {"entities": [], "offerings": [], "facts": [], "has_tracks": [], "rejected": [], "unresolved": []}
        graph = export_graph(self.bundle([first, third]), [(first, [third])], {"p01": empty})
        self.assertFalse([e for e in graph["edges"] if e["type"] == "NEXT_CHUNK"])
        old_ids = {n["id"] for n in graph["nodes"] if n["label"] == "Chunk"}
        revised = [{**c, "version_id": "doc@v2"} for c in (first, third)]
        newer = export_graph(self.bundle(revised), [(revised[0], [revised[1]])], {"p01": empty})
        new_ids = {n["id"] for n in newer["nodes"] if n["label"] == "Chunk"}
        self.assertTrue(old_ids.isdisjoint(new_ids))
        self.assertEqual({n["properties"]["chunk_id"] for n in newer["nodes"] if n["label"] == "Chunk"}, {"doc#0001", "doc#0003"})
        middle = {**first, "pilot_id": "p02", "chunk_id": "doc#0002", "source_index": 1, "role": "context"}
        contiguous = export_graph(self.bundle([first, middle, third]), [(first, [middle, third])], {"p01": empty})
        self.assertEqual(len([e for e in contiguous["edges"] if e["type"] == "NEXT_CHUNK"]), 2)


if __name__ == "__main__":
    unittest.main()
