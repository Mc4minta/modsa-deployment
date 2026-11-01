"""Offline regressions for source-page and metadata compatibility."""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.pipeline.loaders import load_json_documents
from data.pipeline import chunk


class GraphRAGIngestionTests(unittest.TestCase):
    def load_fixture(self, folder: str, metadata: dict) -> list:
        path = Path(folder) / "prepared.json"
        path.write_text(json.dumps({"doc_id": "source", "metadata": metadata,
            "chunks": [{"chunk_id": "source#0001", "content": "Source evidence", "page": 2}]}), encoding="utf-8")
        return load_json_documents(path)

    def test_canonical_and_legacy_page_markers_are_equivalent(self):
        expected = [(1, "First evidence"), (3, "Third evidence")]
        for first, third in [("<!-- page: 1 -->", "<!-- page: 3 -->"),
                             ("<!-- Page 1 -->", "<!-- Page 3 -->"),
                             ("<!--PAGE:1-->", "<!--  pAgE 3 -->")]:
            with self.subTest(marker=first):
                blocks = chunk.parse_blocks(first + "\nFirst evidence\n" + third + "\nThird evidence")
                self.assertEqual([(b.page, b.text()) for b in blocks], expected)

    def test_failed_ocr_marker_updates_page_without_becoming_source_text(self):
        text = "<!-- page: 1 -->\nFirst evidence\n<!-- page: 2 (OCR FAILED) -->\n<!-- Page 3 -->\nThird evidence"
        blocks = chunk.parse_blocks(text)
        self.assertEqual([(b.page, b.text()) for b in blocks], [(1, "First evidence"), (3, "Third evidence")])
        self.assertNotIn("OCR FAILED", "\n".join(b.text() for b in blocks))

    def test_future_document_uses_processing_date_and_only_explicit_policy_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            processed = Path(folder)
            source = processed / "scholarship/example.md"
            source.parent.mkdir()
            source.write_text("<!-- page: 2 -->\n" + "Supported scholarship information. " * 12, encoding="utf-8")
            with patch.object(chunk, "PROCESSED_DIR", processed), patch.object(chunk, "SOURCES", {}):
                document = chunk.build_document(source)
            self.assertEqual(document["doc_id"], "example")
            self.assertEqual(document["chunks"][0]["chunk_id"], "example#0001")
            self.assertEqual(document["chunks"][0]["page"], 2)
            self.assertEqual(document["metadata"]["ingested_at"], date.today().isoformat())
            self.assertNotIn("last_updated", document["metadata"])
            self.assertNotIn("published_at", document["metadata"])
            self.assertNotIn("effective_from", document["metadata"])
            explicit = {"example": {"published_at": "2025-11-11", "effective_from": "2025-11-12", "document_status": "UNKNOWN"}}
            with patch.object(chunk, "PROCESSED_DIR", processed), patch.object(chunk, "SOURCES", explicit):
                document = chunk.build_document(source)
            self.assertEqual(document["metadata"]["published_at"], "2025-11-11")
            self.assertEqual(document["metadata"]["effective_from"], "2025-11-12")

    def test_loader_preserves_false_contact_and_explicit_scalar_contract_fields(self):
        meta = {"verified": False, "contact": "office@example.org", "ingested_at": "2026-10-29",
                "published_at": "2025-11-11", "effective_from": "2025-11-12", "effective_until": None,
                "document_status": "UNKNOWN", "verification_status": "UNVERIFIED", "source_id": "source",
                "source_uri": "data/chunks/example.json", "version_id": "source@hash", "content_hash": "hash",
                "content_type": "application/json"}
        with tempfile.TemporaryDirectory() as folder:
            documents = self.load_fixture(folder, meta)
        self.assertEqual(len(documents), 1)
        loaded = documents[0]
        self.assertEqual(loaded.page_content, "Source evidence")
        self.assertEqual(loaded.metadata["doc_id"], "source")
        self.assertEqual(loaded.metadata["chunk_id"], "source#0001")
        self.assertIs(loaded.metadata["_prechunked"], True)
        self.assertEqual(loaded.metadata["page"], 1)
        self.assertIs(loaded.metadata["verified"], False)
        for key, value in meta.items():
            if value is not None:
                self.assertEqual(loaded.metadata[key], value)
        self.assertNotIn("effective_until", loaded.metadata)

    def test_loader_accepts_legacy_processing_date_without_inventing_new_dates(self):
        with tempfile.TemporaryDirectory() as folder:
            loaded = self.load_fixture(folder, {"last_updated": "2026-10-08", "verified": False})[0]
        self.assertEqual(loaded.metadata["last_updated"], "2026-10-08")
        self.assertIs(loaded.metadata["verified"], False)
        for key in ("ingested_at", "published_at", "effective_from"):
            self.assertNotIn(key, loaded.metadata)

    def test_loader_does_not_forward_unknown_or_unsupported_metadata_values(self):
        meta = {"verified": False, "contact": {"email": "office@example.org"}, "published_at": None,
                "source_uri": ["one", "two"], "ingested_at": "", "version_id": float("nan")}
        with tempfile.TemporaryDirectory() as folder:
            loaded = self.load_fixture(folder, meta)[0]
        self.assertIs(loaded.metadata["verified"], False)
        for key in ("contact", "published_at", "source_uri", "ingested_at", "version_id"):
            self.assertNotIn(key, loaded.metadata)


if __name__ == "__main__":
    unittest.main()
