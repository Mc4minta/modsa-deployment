import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from starlette.requests import Request
from config import Settings
from services import ingestion_service as service
from api.health import health


class IngestionSafetyTests(unittest.TestCase):
    def test_missing_sources_preserve_collection_and_manifest_even_when_forced(self):
        for force in (False,True):
            with self.subTest(force=force),patch.object(service,"discover_source_files",return_value=[]), \
                 patch.object(service,"create_vector_store") as reset,patch.object(service,"save_manifest") as save:
                result=service.ingest_sources(Settings(),force=force)
                self.assertEqual(result["status"],"error")
                reset.assert_not_called()
                save.assert_not_called()

    def test_unreadable_documents_preserve_previous_collection(self):
        with patch.object(service,"discover_source_files",return_value=["source"]), \
             patch.object(service,"build_manifest",return_value={"new":True}), \
             patch.object(service,"load_manifest",return_value=None), \
             patch.object(service,"load_documents",return_value=([],["bad source"])), \
             patch.object(service,"create_vector_store") as reset,patch.object(service,"save_manifest") as save:
            self.assertEqual(service.ingest_sources(Settings())["status"],"error")
            reset.assert_not_called()
            save.assert_not_called()

    def test_empty_chunks_preserve_previous_collection(self):
        with patch.object(service,"discover_source_files",return_value=["source"]), \
             patch.object(service,"build_manifest",return_value={"new":True}), \
             patch.object(service,"load_manifest",return_value=None), \
             patch.object(service,"load_documents",return_value=(["doc"],[])), \
             patch.object(service,"split_documents",return_value=[]), \
             patch.object(service,"create_vector_store") as reset:
            self.assertEqual(service.ingest_sources(Settings())["status"],"error")
            reset.assert_not_called()

    def test_partial_source_loading_does_not_replace_a_complete_index(self):
        with patch.object(service,"discover_source_files",return_value=["valid","invalid"]), \
             patch.object(service,"build_manifest",return_value={"new":True}), \
             patch.object(service,"load_manifest",return_value=None), \
             patch.object(service,"load_documents",return_value=(["doc"],[{"source":"invalid"}])), \
             patch.object(service,"create_vector_store") as reset:
            self.assertEqual(service.ingest_sources(Settings())["status"],"error")
            reset.assert_not_called()

    def test_health_reports_not_ready_until_nonempty_ingestion_succeeds(self):
        for ingestion,expected in ((None,503),({"status":"error"},503),
                ({"status":"empty","files":0},503),({"status":"skipped","files":0},503),
                ({"status":"indexed","files":1},200),({"status":"skipped","files":1},200)):
            with self.subTest(ingestion=ingestion):
                app=SimpleNamespace(state=SimpleNamespace(ingestion=ingestion))
                response=health(Request({"type":"http","app":app}))
                self.assertEqual(response.status_code,expected)
                self.assertEqual(json.loads(response.body)["status"],"ok" if expected==200 else "not_ready")

    def test_valid_ingestion_still_indexes_and_saves_manifest(self):
        store=Mock()
        store._collection.count.return_value=1
        with patch.object(service,"discover_source_files",return_value=["source"]), \
             patch.object(service,"build_manifest",return_value={"new":True}), \
             patch.object(service,"load_manifest",return_value=None), \
             patch.object(service,"load_documents",return_value=(["doc"],[])), \
             patch.object(service,"split_documents",return_value=["chunk"]), \
             patch.object(service,"create_vector_store",return_value=store) as create, \
             patch.object(service,"save_manifest") as save:
            result=service.ingest_sources(Settings())
            self.assertEqual(result["status"],"indexed")
            create.assert_called_once()
            store.add_documents.assert_called_once_with(["chunk"])
            save.assert_called_once()
            self.assertEqual(save.call_args.args[1]["chunks"],1)
            self.assertIn("-build-",save.call_args.args[1]["active_collection"])

    def test_embedding_or_manifest_failure_never_publishes_a_partial_index(self):
        for failure in ("embedding","manifest","count"):
            store=Mock()
            store._collection.count.return_value=65 if failure != "count" else 32
            if failure == "embedding":
                store.add_documents.side_effect=[None,RuntimeError("synthetic embedding failure")]
            with self.subTest(failure=failure), \
                 patch.object(service,"discover_source_files",return_value=["source"]), \
                 patch.object(service,"build_manifest",return_value={"files":["same source"]}), \
                 patch.object(service,"load_manifest",return_value={"active_collection":"old"}), \
                 patch.object(service,"load_documents",return_value=(["doc"],[])), \
                 patch.object(service,"split_documents",return_value=list(range(65))), \
                 patch.object(service,"create_vector_store",return_value=store), \
                 patch.object(service,"get_vector_store") as serving, \
                 patch.object(service,"save_manifest",side_effect=OSError("disk full") if failure=="manifest" else None) as save:
                with self.assertRaises((RuntimeError,OSError,ValueError)):
                    service.ingest_sources(Settings(),force=True)
                store.delete_collection.assert_called_once()
                serving.assert_not_called()
                self.assertEqual(save.call_count,1 if failure=="manifest" else 0)

    def test_count_mismatch_rebuilds_instead_of_skipping_partial_collection(self):
        store=Mock();store._collection.count.return_value=1
        settings=Settings()
        previous={"files":["source"],"collection_base":settings.chroma_collection,"chunks":65,
                  "index_config":{"embedding_provider":settings.embedding_provider,"embedding_model":settings.embedding_model,
                  "embedding_base_url":settings.embedding_base_url,"chunk_size":settings.chunk_size,"chunk_overlap":settings.chunk_overlap}}
        with patch.object(service,"discover_source_files",return_value=["source"]), \
             patch.object(service,"build_manifest",return_value={"files":["source"]}), \
             patch.object(service,"load_manifest",return_value=previous), \
             patch.object(service,"collection_document_count",return_value=32), \
             patch.object(service,"load_documents",return_value=(["doc"],[])), \
             patch.object(service,"split_documents",return_value=["chunk"]), \
             patch.object(service,"create_vector_store",return_value=store),patch.object(service,"save_manifest"):
            self.assertEqual(service.ingest_sources(settings)["status"],"indexed")


if __name__ == "__main__":
    unittest.main()
