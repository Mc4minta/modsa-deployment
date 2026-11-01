"""Offline intent and heading-scope guards; no model, embedding or DB calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

from langchain_core.documents import Document
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from schemas.retrieval import QueryIntent
from services.query_service import PilotScopeFilter, parse_query_intent


def source_doc(
    chunk="a", text="รอบที่ 1 (ปีการศึกษา 2569)", *, index=0,
    source="source", version="source@v1", digest="a" * 64, category="scholarship",
):
    return Document(page_content=text, metadata={
        "source_id": source, "version_id": version, "content_hash": digest,
        "chunk_id": chunk, "source_index": index, "category": category,
        "document_status": "UNKNOWN", "retrieval_enabled": False,
    })


class QueryIntentTests(unittest.TestCase):
    def test_contract_rejects_unknown_categories_extra_fields_and_noninteger_years(self):
        for values in (
            {"categories": ["admin"]}, {"cypher": "MATCH (n) RETURN n"},
            {"academic_years": [True]}, {"academic_years": ["2569"]},
            {"rounds": [False]}, {"rounds": [0]},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                QueryIntent(**values)

    def test_two_academic_years_and_two_categories_are_not_collapsed(self):
        intent = parse_query_intent("จำนวนทุนปี 2568 กับปี 2569 ต่างกันอย่างไร?")
        self.assertEqual(intent.categories, ["scholarship"])
        self.assertEqual(intent.academic_years, [2568, 2569])
        intent = parse_query_intent("นักศึกษา probation ต้องทำอะไร และติดต่อเบอร์ใด?")
        self.assertEqual(set(intent.categories), {"registration", "others"})
        self.assertEqual(intent.academic_years, [])

    def test_thai_digits_are_normalized_without_inventing_scope(self):
        intent = parse_query_intent("ทุนปี ๒๕๖๙ รอบที่ ๑ มีกี่ทุน?")
        self.assertEqual(intent.academic_years, [2569])
        self.assertEqual(intent.rounds, [1])

    def test_negated_year_disables_only_year_filter(self):
        intent = parse_query_intent("ไม่เอาปี 2568 ขอทุนปี 2569 รอบ 1")
        self.assertEqual(intent.academic_years, [])
        self.assertEqual(intent.rounds, [1])
        self.assertEqual(intent.categories, ["scholarship"])
        self.assertIn("negated_year", intent.ambiguities)

    def test_negated_round_is_not_a_positive_round_filter(self):
        for question in ("ทุนปี 2569 ไม่ใช่รอบ 1", "ทุนปี 2569 ยกเว้นรอบ 1"):
            with self.subTest(question=question):
                intent = parse_query_intent(question)
                self.assertEqual(intent.rounds, [])
                self.assertEqual(intent.academic_years, [2569])
                self.assertIn("negated_round", intent.ambiguities)

    def test_negated_category_does_not_supply_an_academic_year_filter(self):
        intent = parse_query_intent("ไม่เอาทุน ขอค่าใช้จ่ายปี 2569")
        self.assertEqual(intent.categories, [])
        self.assertEqual(intent.academic_years, [])
        self.assertEqual(intent.rounds, [])
        self.assertIn("negated_category", intent.ambiguities)

    def test_ranges_and_comparisons_are_not_endpoint_equality_filters(self):
        for question, ambiguity in (
            ("ทุนปี 2568 ถึง 2570", "year_range"),
            ("ทุนปี ๒๕๖๘–๒๕๗๐", "year_range"),
            ("ทุนระหว่างปี 2568 กับปี 2570", "year_range"),
            ("ทุนก่อนปี 2569", "year_comparison"),
            ("ทุนหลัง พ.ศ. 2569", "year_comparison"),
            ("ทุนหลังปีการศึกษา 2569", "year_comparison"),
            ("ทุนปี 2569 เป็นต้นไป", "year_comparison"),
        ):
            with self.subTest(question=question):
                intent = parse_query_intent(question)
                self.assertEqual(intent.academic_years, [])
                self.assertIn(ambiguity, intent.ambiguities)
        intent = parse_query_intent("ทุนปี 2569 รอบ 1 ถึง 3")
        self.assertEqual(intent.rounds, [])
        self.assertEqual(intent.academic_years, [2569])
        self.assertIn("round_range", intent.ambiguities)
        for question in ("ทุนปี 2569 ก่อนรอบ 2", "ทุนปี 2569 รอบ 2 ขึ้นไป"):
            with self.subTest(question=question):
                intent = parse_query_intent(question)
                self.assertEqual(intent.rounds, [])
                self.assertIn("round_comparison", intent.ambiguities)

    def test_relative_time_does_not_use_the_runtime_year_or_current_policy(self):
        intent = parse_query_intent("ทุนปีนี้ฉบับล่าสุดที่ใช้ปัจจุบัน")
        self.assertEqual(intent.academic_years, [])
        self.assertEqual(intent.rounds, [])
        self.assertIn("current_applicability_unknown", intent.ambiguities)

    def test_ordinary_or_not_question_is_not_negated_scope(self):
        intent = parse_query_intent("ทุนปี 2569 รอบ 1 มีจำนวน 15 ทุนหรือไม่?")
        self.assertEqual(intent.academic_years, [2569])
        self.assertEqual(intent.rounds, [1])
        self.assertEqual(intent.ambiguities, [])

    def test_regulation_edition_and_fee_asof_year_are_not_academic_years(self):
        for question in (
            "ข้อบังคับวินัยปี 2566 ยกเลิกฉบับปีใด?",
            "ข้อมูล ณ วันที่ 12 มีนาคม 2569 ในตารางค่าใช้จ่ายยืนยันวันมีผลได้ไหม?",
        ):
            with self.subTest(question=question):
                self.assertEqual(parse_query_intent(question).academic_years, [])

    def test_unclear_category_means_no_hard_category_filter(self):
        self.assertEqual(parse_query_intent("คณิตศาสตร์ ในหน้าที่เลือก รับวุฒิใด?").categories, [])

    def test_invalid_zero_round_does_not_create_an_invalid_query_contract(self):
        intent = parse_query_intent("ทุนปี 2569 รอบ 0")
        self.assertEqual(intent.rounds, [])
        self.assertIn("invalid_round", intent.ambiguities)


class PilotScopeFilterTests(unittest.TestCase):
    def test_leading_formal_header_supplies_same_version_scope_and_exact_evidence(self):
        header = source_doc(text="[ทุน | misleading-2568]\nรอบที่ 1 (ปีการศึกษา 2569)")
        body = source_doc("b", "จำนวน 15 ทุน", index=1)
        scope_filter = PilotScopeFilter([header, body])
        scope = scope_filter.describe()[0]
        self.assertEqual((scope["academic_year"], scope["round"]), (2569, 1))
        self.assertEqual(scope["evidence"][0]["quote"], "รอบที่ 1 (ปีการศึกษา 2569)")
        self.assertTrue(scope["evidence"][0]["leading_header"])
        kept, decisions = scope_filter.apply([body], QueryIntent(academic_years=[2568]))
        self.assertEqual(kept, [])
        self.assertEqual(decisions[0]["reasons"], ["academic_year_mismatch"])

    def test_calendar_title_year_is_not_a_policy_status(self):
        document = source_doc(text="เรื่อง ปฏิทินการศึกษา ประจำปีการศึกษา 2569", category="academic_calendar")
        before = deepcopy(document)
        scope = PilotScopeFilter([document]).describe()[0]
        self.assertEqual(scope["academic_year"], 2569)
        self.assertEqual(scope["scope_kind"], "experimental_document_heading_not_policy_status")
        self.assertIsNone(scope["round"])
        self.assertEqual(document, before)
        self.assertEqual(document.metadata["document_status"], "UNKNOWN")
        self.assertIs(document.metadata["retrieval_enabled"], False)

    def test_thai_header_digits_keep_original_quote_offsets(self):
        text = "[ทุน | header]\nรอบที่ ๑ (ปีการศึกษา ๒๕๖๙)"
        scope = PilotScopeFilter([source_doc(text=text)]).describe()[0]
        self.assertEqual((scope["academic_year"], scope["round"]), (2569, 1))
        self.assertEqual(scope["evidence"][0]["quote"], "รอบที่ ๑ (ปีการศึกษา ๒๕๖๙)")
        self.assertIn(scope["evidence"][0]["quote"], text)

    def test_filename_body_reference_and_asof_date_do_not_become_scope(self):
        for text, category in (
            ("[ทุน | ปีการศึกษา 2569]\nจำนวน 15 ทุน", "scholarship"),
            ("นักศึกษาเคยได้รับทุนในปีการศึกษา 2569", "scholarship"),
            ("ข้อมูล ณ วันที่ 12 มีนาคม 2569", "fees"),
            ("ข้อบังคับว่าด้วยวินัย พ.ศ. 2566", "academic_rules"),
        ):
            with self.subTest(text=text):
                scope = PilotScopeFilter([source_doc(text=text, category=category)]).describe()[0]
                self.assertIsNone(scope["academic_year"])
                self.assertIsNone(scope["round"])

    def test_header_after_leading_window_or_without_chunk_zero_is_unknown(self):
        for document in (
            source_doc(text="x" * 610 + "\nรอบที่ 1 (ปีการศึกษา 2569)"),
            source_doc(text="รอบที่ 1 (ปีการศึกษา 2569)", index=1),
        ):
            with self.subTest(index=document.metadata["source_index"]):
                scope_filter = PilotScopeFilter([document])
                self.assertIsNone(scope_filter.describe()[0]["academic_year"])
                kept, decisions = scope_filter.apply([document], QueryIntent(academic_years=[2570]))
                self.assertEqual(kept, [document])
                self.assertIn("academic_year", decisions[0]["unknown_fields"])

    def test_conflicting_year_headers_disable_year_and_round_scope(self):
        first = source_doc()
        conflict = source_doc("b", "รอบที่ 1 (ปีการศึกษา 2568)", index=1)
        scope_filter = PilotScopeFilter([first, conflict])
        scope = scope_filter.describe()[0]
        self.assertIsNone(scope["academic_year"])
        self.assertIsNone(scope["round"])
        kept, decisions = scope_filter.apply([first], QueryIntent(academic_years=[2570], rounds=[2]))
        self.assertEqual(kept, [first])
        self.assertEqual(set(decisions[0]["unknown_fields"]), {"academic_year", "round"})

    def test_conflicting_rounds_keep_known_year_but_do_not_choose_a_round(self):
        first = source_doc()
        second = source_doc("b", "รอบที่ 2 (ปีการศึกษา 2569)", index=1)
        scope_filter = PilotScopeFilter([first, second])
        scope = scope_filter.describe()[0]
        self.assertEqual(scope["academic_year"], 2569)
        self.assertIsNone(scope["round"])
        kept, decisions = scope_filter.apply([first], QueryIntent(academic_years=[2569], rounds=[2]))
        self.assertEqual(kept, [first])
        self.assertEqual(decisions[0]["unknown_fields"], ["round"])

    def test_source_version_hash_and_exact_content_isolate_scope(self):
        original = source_doc()
        another_version = source_doc("b", "จำนวน 20 ทุน", version="source@v2", digest="b" * 64)
        scope_filter = PilotScopeFilter([original, another_version])
        for changed in (
            another_version,
            source_doc(version="source@foreign"),
            source_doc(digest="c" * 64),
            source_doc(source="another-source"),
            source_doc(text=original.page_content + " changed"),
        ):
            with self.subTest(metadata=changed.metadata):
                kept, decisions = scope_filter.apply([changed], QueryIntent(academic_years=[2570], rounds=[2]))
                self.assertEqual(kept, [changed])
                self.assertEqual(set(decisions[0]["unknown_fields"]), {"academic_year", "round"})

    def test_unknown_category_and_missing_scope_identity_are_retained(self):
        for metadata in ({}, {"category": "unknown"}, {"category": None}):
            document = Document(page_content="unscoped reference", metadata=metadata)
            scope_filter = PilotScopeFilter([document])
            kept, decisions = scope_filter.apply([document], QueryIntent(categories=["scholarship"], academic_years=[2569]))
            with self.subTest(metadata=metadata):
                self.assertEqual(kept, [document])
                self.assertEqual(decisions[0]["reasons"], [])
                self.assertEqual(set(decisions[0]["unknown_fields"]), {"category", "academic_year"})

    def test_malformed_metadata_is_unknown_not_a_crash_or_coerced_identity(self):
        for field in ("source_id", "version_id", "content_hash", "category", "chunk_id"):
            document = source_doc()
            document.metadata[field] = ["malformed-value"]
            scope_filter = PilotScopeFilter([document]) if field != "chunk_id" else PilotScopeFilter([])
            kept, decisions = scope_filter.apply([document], QueryIntent(categories=["scholarship"], academic_years=[2570]))
            with self.subTest(field=field):
                self.assertEqual(kept, [document])
                self.assertIn("academic_year", decisions[0]["unknown_fields"])

    def test_known_category_mismatch_is_rejected_even_when_year_is_unknown(self):
        document = source_doc(text="ข้อมูลค่าใช้จ่าย", category="fees")
        kept, decisions = PilotScopeFilter([document]).apply([document], QueryIntent(categories=["scholarship"]))
        self.assertEqual(kept, [])
        self.assertEqual(decisions[0]["reasons"], ["category_mismatch"])

    def test_duplicate_scope_chunk_identity_is_rejected(self):
        document = source_doc()
        with self.assertRaisesRegex(ValueError, "Duplicate chunk"):
            PilotScopeFilter([document, deepcopy(document)])

    def test_filtering_does_not_mutate_sources_or_intent(self):
        documents = [source_doc(), source_doc("b", "จำนวน 15 ทุน", index=1)]
        before = deepcopy(documents)
        intent = QueryIntent(categories=["scholarship"], academic_years=[2568], rounds=[1])
        original_intent = intent.model_dump()
        scope_filter = PilotScopeFilter(documents)
        scope_filter.apply(documents, intent)
        self.assertEqual(documents, before)
        self.assertEqual(intent.model_dump(), original_intent)


if __name__ == "__main__":
    unittest.main()
