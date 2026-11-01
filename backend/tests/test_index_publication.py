"""Use an isolated real Chroma store and deterministic, offline embeddings."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chromadb.config import Settings as ChromaSettings
from langchain_core.embeddings import Embeddings

from config import Settings
from core import vectorstore
from services.ingestion_service import ingest_sources


class OfflineEmbeddings(Embeddings):
    def __init__(self):
        self.calls = 0
        self.fail_at = None

    def embed_documents(self, texts):
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError("Synthetic embedding failure")
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 0.0]


class IndexPublicationTests(unittest.TestCase):
    def tearDown(self):
        vectorstore.reset_vector_store_cache()

    def test_failed_forced_reindex_keeps_complete_active_index_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.json"
            source.write_text(json.dumps({"doc_id":"test","metadata":{},"chunks":[
                {"chunk_id":f"test#{i}","content":f"Original knowledge {i}","page":1} for i in range(65)]}))
            settings = Settings(_env_file=None, CHROMA_DIR=root/"chroma", CHROMA_COLLECTION="test_publication",
                                RAG_SOURCE_PATHS=str(source))
            embeddings = OfflineEmbeddings()
            real_chroma = vectorstore.Chroma

            def local_store(**kwargs):
                return real_chroma(**kwargs, client_settings=ChromaSettings(anonymized_telemetry=False))

            with patch.object(vectorstore,"build_embeddings",return_value=embeddings), \
                 patch.object(vectorstore,"Chroma",side_effect=local_store):
                self.assertEqual(ingest_sources(settings)["chunks"],65)
                old = vectorstore.get_vector_store(settings)
                manifest = (settings.chroma_dir/vectorstore.MANIFEST_FILE).read_bytes()
                embeddings.fail_at = embeddings.calls + 2
                with self.assertRaisesRegex(RuntimeError,"Synthetic"):
                    ingest_sources(settings,force=True)
                self.assertEqual((settings.chroma_dir/vectorstore.MANIFEST_FILE).read_bytes(),manifest)
                self.assertIs(vectorstore.get_vector_store(settings),old)
                self.assertEqual(old._collection.count(),65)
                self.assertEqual(ingest_sources(settings)["status"],"skipped")
                embeddings.fail_at = None
                self.assertEqual(ingest_sources(settings,force=True)["status"],"indexed")
                current = vectorstore.get_vector_store(settings)
                self.assertNotEqual(current._collection.name,old._collection.name)
                self.assertEqual(current._collection.count(),65)
                # Requests already using the previous wrapper still have a complete index.
                self.assertEqual(old._collection.count(),65)
                self.assertTrue(current.similarity_search("knowledge",k=1))
                vectorstore.reset_vector_store_cache()
                self.assertEqual(vectorstore.get_vector_store(settings)._collection.name,current._collection.name)

    def test_atomic_manifest_failure_preserves_previous_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(_env_file=None,CHROMA_DIR=Path(folder))
            old = {"active_collection":"old","chunks":65}
            vectorstore.save_manifest(settings,old)
            with patch.object(vectorstore.os,"replace",side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    vectorstore.save_manifest(settings,{"active_collection":"partial","chunks":32})
            self.assertEqual(vectorstore.load_manifest(settings),old)
            self.assertEqual([p.name for p in Path(folder).iterdir()],[vectorstore.MANIFEST_FILE])


if __name__ == "__main__":
    unittest.main()
