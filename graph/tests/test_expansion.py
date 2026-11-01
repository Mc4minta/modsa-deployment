from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"graph/build"))
import expand
import contracts


class ExpansionTests(unittest.TestCase):
    @contextmanager
    def fixture(self, counts=(1,1)):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            base=root/"data/chunks/registration"
            base.mkdir(parents=True)
            data=root/"graph/data"
            (data/"inputs").mkdir(parents=True)
            (data/"inputs/schema.json").write_bytes((ROOT/"graph/data/inputs/schema.json").read_bytes())
            for i,count in enumerate(counts):
                (base/f"document{i}.json").write_text(json.dumps({"doc_id":f"source{i}","metadata":{},
                    "chunks":[{"chunk_id":f"source{i}#{n}","content":f"การลงทะเบียน ต้องยืนยันในระบบ ขั้นตอน{n}","page":1}
                              for n in range(count)]},ensure_ascii=False))
            with patch.object(expand,"ROOT",root),patch.object(contracts,"ROOT",root), \
                 patch.object(expand,"DATA",data),patch.object(expand,"OUTPUT",root/"graph/expansions"):
                yield root,base

    def record(self, primary, contexts, schema):
        evidence=[{"chunk_id":primary["chunk_id"],"quote":primary["content"]}]
        return {"extraction":{"entities":[{"ref":"e","kind":"procedure","name":"การลงทะเบียน",
            "scope_text":"ตามข้อความ","evidence":evidence}],"offerings":[],"facts":[{
            "ref":"f","subject_refs":["e"],"kind":"rule","predicate":"confirmation",
            "raw_text":primary["content"],"value_number":None,"value_text":"ต้องยืนยันในระบบ",
            "operator":None,"unit":None,"scope_text":"ตามข้อความ","is_approximate":False,"evidence":evidence}],
            "has_tracks":[],"unresolved":[]}}

    def test_arbitrary_counts_no_pilot_questions_and_generic_focus(self):
        with self.fixture((4,2)) as (root,base):
            batch=expand.prepare(base)
            self.assertEqual([len(d["jobs"]) for d in batch["documents"]],[4,2])
            self.assertFalse((root/"graph/data/inputs/questions.json").exists())
            for d in batch["documents"]:
                for job in d["jobs"]:
                    payload=expand.request_payload(job["primary"],job["contexts"],batch["schema"])
                    self.assertEqual(json.loads(payload["messages"][1]["content"])["focus"],expand.FOCUS)
                    self.assertTrue(all(c["version_id"]==job["primary"]["version_id"] for c in job["contexts"]))

    def test_check_is_offline_no_key_files_or_db(self):
        with self.fixture() as (_,base),patch.object(sys,"argv",["expand.py","--input",str(base),"--check"]), \
             patch.object(expand,"api_key",side_effect=AssertionError("key")), \
             patch.object(expand,"call",side_effect=AssertionError("API")), \
             patch.object(expand,"save",side_effect=AssertionError("write")), \
             patch.object(expand,"load",side_effect=AssertionError("DB")),redirect_stdout(io.StringIO()):
            expand.main()

    def test_budget_rejects_before_any_request(self):
        with self.fixture() as (_,base),patch.object(expand,"call") as call:
            with self.assertRaisesRegex(ValueError,"Need 2"):
                expand.extract_missing(expand.prepare(base),1)
            call.assert_not_called()

    def test_repeated_input_uses_cache_and_new_document_keeps_existing_runs(self):
        with self.fixture() as (_,base),patch.object(expand,"call",side_effect=self.record) as call,redirect_stdout(io.StringIO()):
            first=expand.prepare(base)
            self.assertEqual(expand.extract_missing(first,2),2)
            output=expand.package(first)
            self.assertEqual(expand.extract_missing(first,0),0)
            self.assertEqual(output,expand.package(first))
            self.assertEqual(call.call_count,2)
            (base/"document2.json").write_text(json.dumps({"doc_id":"new","metadata":{},"chunks":[
                {"chunk_id":"new#1","content":"การลงทะเบียน ต้องยืนยันในระบบ","page":1}]},ensure_ascii=False))
            second=expand.prepare(base)
            self.assertEqual(expand.extract_missing(second,1),1)
            self.assertEqual([d["run_id"] for d in output["documents"]],
                             [d["run_id"] for d in expand.package(second)["documents"][:2]])
            self.assertNotEqual(first["batch_id"],second["batch_id"])

    def test_changed_document_requires_only_that_version_to_be_extracted(self):
        with self.fixture() as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            original=expand.prepare(base)
            expand.extract_missing(original,2)
            path=base/"document0.json"
            source=json.loads(path.read_text());source["chunks"][0]["content"]+=" เพิ่มเติม"
            path.write_text(json.dumps(source,ensure_ascii=False))
            changed=expand.prepare(base)
            self.assertNotEqual(original["documents"][0]["jobs"][0]["key"],changed["documents"][0]["jobs"][0]["key"])
            self.assertEqual(original["documents"][1],changed["documents"][1])
            self.assertEqual(expand.extract_missing(changed,1),1)

    def test_rejects_external_paths_duplicates_and_empty_documents(self):
        with self.fixture() as (root,base):
            with self.assertRaises(ValueError):expand.prepare(root)
            source=json.loads((base/"document0.json").read_text())
            (base/"duplicate.json").write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,"Duplicate source"):
                expand.prepare(base)
            (base/"duplicate.json").unlink()
            source["chunks"]=[]
            (base/"document0.json").write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,"without chunks"):
                expand.prepare(base)

    def test_corrupt_cache_cannot_trigger_an_api_fallback(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call") as call:
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),{"request_hash":"wrong"})
            with self.assertRaisesRegex(ValueError,"identity mismatch"):
                expand.extract_missing(batch,1)
            call.assert_not_called()

    def test_invalid_quote_fails_without_export_and_keeps_successful_cache(self):
        def bad(primary,contexts,schema):
            record=self.record(primary,contexts,schema)
            record["extraction"]["facts"][0]["raw_text"]="fabricated"
            return record
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=bad),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base)
            with self.assertRaisesRegex(ValueError,"Extraction stopped"):
                expand.extract_missing(batch,1)
            self.assertTrue(list((expand.OUTPUT/"cache").glob("*.json")))
            self.assertFalse((expand.OUTPUT/"batches").exists())
            with self.assertRaises(ValueError):expand.package(batch)

    def test_provider_error_is_redacted_no_retry(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=RuntimeError("SECRET")) as call,redirect_stdout(io.StringIO()):
            batch=expand.prepare(base)
            with self.assertRaises(ValueError):expand.extract_missing(batch,1)
            call.assert_called_once()
            self.assertNotIn("SECRET",next((expand.OUTPUT/"cache").glob("*.json")).read_text())

    def test_export_is_pending_and_quoted_with_source_backbone(self):
        with self.fixture((2,)) as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);expand.extract_missing(batch,2)
            output=expand.package(batch);graph=output["documents"][0]["graph"]
            self.assertTrue(all(n["properties"]["review_status"]=="PENDING" and n["properties"]["retrieval_enabled"] is False for n in graph["nodes"]))
            types={e["type"] for e in graph["edges"]}
            self.assertTrue({"HAS_VERSION","HAS_CHUNK","NEXT_CHUNK","ABOUT","SUPPORTED_BY"}<=types)
            self.assertTrue(output["documents"][0]["run_id"].startswith("modsa-expansion-v1:"))

    def test_no_supported_facts_can_export_source_backbone_with_unresolved_note(self):
        empty={"extraction":{"entities":[],"offerings":[],"facts":[],"has_tracks":[],
                             "unresolved":["No semantic facts established"]}}
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",return_value=empty),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);expand.extract_missing(batch,1)
            output=expand.package(batch)
            self.assertEqual({n["label"] for n in output["documents"][0]["graph"]["nodes"]},
                             {"SourceDocument","DocumentVersion","Chunk"})
            self.assertTrue(output["documents"][0]["unresolved"][0]["notes"])

    def test_load_requires_the_exact_current_built_package(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);expand.extract_missing(batch,1)
            with patch.object(sys,"argv",["expand.py","--input",str(base),"--load"]), \
                 patch.object(expand,"load") as load,redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):expand.main()
                load.assert_not_called()

    def test_cli_extract_build_and_load_use_the_same_validated_package(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            with patch.object(sys,"argv",["expand.py","--input",str(base),"--extract","--max-calls","1"]):
                expand.main()
            batch=expand.prepare(base)
            path=expand.OUTPUT/"batches"/batch["batch_id"]/"graph.json"
            self.assertEqual(expand.read(path),expand.package(batch))
            self.assertTrue((path.parent/"README.md").exists())
            with patch.object(sys,"argv",["expand.py","--input",str(base),"--load"]), \
                 patch.object(expand,"load",return_value={"documents":1,"nodes_created":5,"relationships_created":5}) as load:
                expand.main()
                load.assert_called_once()

    def test_failed_build_does_not_replace_previous_export(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);expand.extract_missing(batch,1)
            path=expand.OUTPUT/"batches"/batch["batch_id"]/"graph.json"
            expand.save(path,expand.package(batch));before=path.read_bytes()
            job=batch["documents"][0]["jobs"][0]
            cache=expand.OUTPUT/"cache"/(job["key"]+".json")
            record=expand.read(cache);record["extraction"]["facts"][0]["raw_text"]="invalid"
            expand.save(cache,record)
            with patch.object(sys,"argv",["expand.py","--input",str(base),"--build"]),redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):expand.main()
            self.assertEqual(path.read_bytes(),before)

    def test_batch_import_checks_idempotency_in_one_transaction(self):
        plans=[{"run_id":"a"},{"run_id":"b"}]
        with patch.object(expand,"other_content",return_value={"fingerprint":"same"}) as outside, \
             patch.object(expand,"assert_run") as readback,patch.object(expand,"merge_run",side_effect=[
            {"nodes_created":2,"relationships_created":1,"content_hash":"a"},{"nodes_created":3,"relationships_created":2,"content_hash":"b"},
            {"nodes_created":0,"relationships_created":0,"content_hash":"a"},{"nodes_created":0,"relationships_created":0,"content_hash":"b"}]) as merge:
            result=expand.merge_batch("transaction",plans)
            self.assertEqual(result,{"documents":2,"nodes_created":5,"relationships_created":3})
            self.assertTrue(all(c.args[0]=="transaction" for c in merge.call_args_list))
            self.assertTrue(all(c.kwargs=={"check_unrelated":False} for c in merge.call_args_list))
            self.assertEqual(outside.call_count,2)
            self.assertEqual(outside.call_args.args[1],["a","b"])
            self.assertEqual(readback.call_count,2)
        with patch.object(expand,"other_content",return_value={}), \
             patch.object(expand,"merge_run",return_value={"nodes_created":1,"relationships_created":0}):
            with self.assertRaisesRegex(ValueError,"rollback"):
                expand.merge_batch("transaction",plans)

    def test_batch_guard_detects_unrelated_changes_with_constant_scan_count(self):
        plans=[{"run_id":str(i)} for i in range(71)]
        with patch.object(expand,"other_content",side_effect=[{"fingerprint":"old"},{"fingerprint":"changed"}]) as outside, \
             patch.object(expand,"assert_run"),patch.object(expand,"merge_run",return_value={
                 "nodes_created":0,"relationships_created":0,"content_hash":"same"}):
            with self.assertRaisesRegex(ValueError,"Unrelated graph changed"):
                expand.merge_batch("transaction",plans)
            self.assertEqual(outside.call_count,2)

    def test_expansion_retains_lifecycle_metadata_without_changing_frozen_pilot(self):
        frozen=(ROOT/"graph/data/inputs/schema.json").read_bytes()
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=self.record),redirect_stdout(io.StringIO()):
            path=base/"document0.json";source=json.loads(path.read_text())
            source["metadata"]={"source_url":"https://example.org/policy","effective_from":"2026-01-01",
                "effective_until":"2026-12-31","ingested_at":"2026-10-01","supersedes":["source0@older"]}
            path.write_text(json.dumps(source,ensure_ascii=False))
            batch=expand.prepare(base);expand.extract_missing(batch,1)
            graph=expand.package(batch)["documents"][0]["graph"]
            nodes={n["label"]:n["properties"] for n in graph["nodes"]}
            self.assertEqual(nodes["SourceDocument"]["source_uri"],"https://example.org/policy")
            self.assertEqual(nodes["DocumentVersion"]["effective_until"],"2026-12-31")
            self.assertEqual(nodes["DocumentVersion"]["supersedes"],["source0@older"])
            self.assertEqual(nodes["DocumentVersion"]["ingested_at"],"2026-10-01")
            plan=expand.document_plan(graph,batch["schema"])
            self.assertIn("source-metadata-v1",plan["schema_version"])
            broken=copy.deepcopy(graph)
            next(n for n in broken["nodes"] if n["label"]=="DocumentVersion")["properties"]["supersedes"]=[1]
            with self.assertRaises(ValueError):expand.document_plan(broken,batch["schema"])
        self.assertEqual((ROOT/"graph/data/inputs/schema.json").read_bytes(),frozen)


if __name__ == "__main__":
    unittest.main()
