"""Full corpus sidecar validation and explicit numeric-range semantics."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graph/build"))
from contracts import Chunk, DocumentVersion, NumericRange, ROOT, SourceNotes, adapt, build_contracts
import contracts
from common import fingerprint


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

    def test_check_needs_no_saved_json_markdown_or_writes(self):
        result = build_contracts()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(contracts,"DATA",root),patch.object(contracts,"build_contracts",return_value=result), \
                 patch.object(sys,"argv",["contracts.py","--check"]), \
                 patch.object(Path,"write_text",side_effect=AssertionError("check must not write")),redirect_stdout(io.StringIO()):
                contracts.main()
            self.assertFalse(list(root.rglob("*.md")))

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


if __name__ == "__main__":
    unittest.main()
