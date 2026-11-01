"""Full corpus sidecar validation and explicit numeric-range semantics."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graph/build"))
from contracts import Chunk, DocumentVersion, NumericRange, ROOT, SourceNotes, adapt, build_contracts, render_report
import prepare as prep
from prepare import fingerprint


class KnowledgeContractTests(unittest.TestCase):
    def setUp(self):
        self.document = {"doc_id": "test", "metadata": {"title": "Example", "last_updated": "2026-10-08", "verified": False},
                         "chunks": [{"chunk_id": "test#0001", "content": "ข้อมูล", "page": 2}]}
        self.path = ROOT / "data/chunks/others/test.json"

    def test_adapter_preserves_legacy_ids_and_never_infers_policy_dates(self):
        original = copy.deepcopy(self.document)
        record, missing = adapt(self.path, self.document, {})
        self.assertEqual(self.document, original)
        self.assertEqual(record["chunks"][0]["legacy_chunk_id"], "test#0001")
        self.assertTrue(record["chunks"][0]["chunk_id"].startswith(record["version"]["version_id"]))
        self.assertEqual(record["version"]["ingested_at"], "2026-10-08")
        self.assertEqual(record["version"]["verification_status"], "UNVERIFIED")
        self.assertIsNone(record["version"]["published_at"])
        self.assertIsNone(record["version"]["effective_from"])
        self.assertIn("document_status", missing)

    def test_ids_and_effective_intervals_are_validated(self):
        digest = fingerprint([{"content": "test"}])
        common = {"source_id": "s", "version_id": f"s@{digest[:16]}", "content_hash": digest}
        with self.assertRaises(ValueError):
            DocumentVersion(**common, effective_from="2026-10-02", effective_until="2026-10-01")
        with self.assertRaises(ValueError):
            Chunk(chunk_id="legacy#1", legacy_chunk_id="legacy#1", version_id="s@v1", content="text", chunk_index=1)

    def test_between_preserves_unknown_endpoint_inclusivity_and_rejects_bad_bounds(self):
        value = NumericRange(lower=6501, upper=12500)
        self.assertIsNone(value.lower_inclusive)
        self.assertIsNone(value.upper_inclusive)
        for values in ({"lower": 5, "upper": 2}, {"lower": "5", "upper": 8}, {"lower": True, "upper": 8},
                       {"lower": 5, "upper": 5, "lower_inclusive": False}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                NumericRange(**values)

    def test_current_corpus_has_valid_distinct_sidecar_ids(self):
        result = build_contracts()
        self.assertFalse(result["errors"])
        sources = list((ROOT/"data/chunks").rglob("*.json"))
        self.assertEqual(result["counts"]["files"], len(sources))
        self.assertEqual(result["counts"]["chunks"], sum(len(json.loads(p.read_text())["chunks"]) for p in sources))
        ids = [c["chunk_id"] for r in result["records"] for c in r["chunks"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_report_keeps_owner_audit_without_making_it_a_pilot_gate(self):
        result = build_contracts()
        original = copy.deepcopy(result)
        report = render_report(result)
        self.assertIn("ไม่ใช่เงื่อนไขรอทีม Data", report)
        self.assertIn("ไม่ใช่ field บังคับหรือเงื่อนไขหยุด pilot", report)
        self.assertIn("ยังไม่ได้สกัดวันที่/สถานะจากเนื้อหาครบทั้งคลัง", report)
        self.assertEqual(result, original)

    def test_explicit_source_uri_is_preserved(self):
        record, missing = adapt(self.path, self.document, {"source_uri": "https://example.org/original.pdf", "content_type": "application/pdf"})
        self.assertEqual(record["source"]["source_uri"], "https://example.org/original.pdf")
        self.assertEqual(record["source"]["content_type"], "application/pdf")
        self.assertNotIn("official_source_url", missing)

    def test_date_values_cannot_coerce_timestamps_or_unlabelled_be_dates(self):
        digest = fingerprint([{"content": "test"}])
        common = {"source_id": "s", "version_id": f"s@{digest[:16]}", "content_hash": digest}
        for value in (86400, False, "2569-01-01", "2026-01-01T00:00:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                DocumentVersion(**common, published_at=value)
            with self.subTest(note=value), self.assertRaises(ValueError):
                SourceNotes(published_at=value)

    def test_pilot_projection_accepts_full_contract_notes_without_rewriting_ids(self):
        original = prep.read
        source_id = prep.build()["sources"][0]["source_id"]
        notes = {source_id: {"effective_until": "2027-01-01", "supersedes": [], "source_uri": "https://example.org/source.pdf", "verified": True}}
        with patch.object(prep, "read", side_effect=lambda p: notes if p.name == "source_notes.json" else original(p)), patch.object(Path, "exists", return_value=True):
            bundle = prep.build()
        self.assertEqual(bundle["sources"][0]["verification_status"], "VERIFIED")
        self.assertEqual(bundle["sources"][0]["source_id"], source_id)
        self.assertEqual(len(bundle["pilot"]), 27)


if __name__ == "__main__":
    unittest.main()
