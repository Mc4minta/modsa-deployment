from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"graph/build"))
import expand
import contracts
import common


class ExpansionTests(unittest.TestCase):
    def write_review(self, job, record, action, changes=None):
        edit={"ref":"f","before_hash":expand.fingerprint(record["extraction"]["facts"][0]),
              "action":action,"reason":"Source interpretation pending; retain complete source and exceptions."}
        if changes is not None:edit["changes"]=changes
        review={"format":"modsa-source-review-v1","request_hash":job["key"],
                "base_record_hash":expand.fingerprint(record),"reviewer":"codex-source-review",
                "policy_status":"PENDING","edits":[edit]}
        expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),record)
        expand.save(expand.OUTPUT/"reviews"/(job["key"]+".json"),review)
        return review

    def test_source_review_restores_explicit_bound_without_changing_response(self):
        with self.fixture((1,),content="การลงทะเบียน อย่างน้อย 3 หน่วยกิต ยกเว้น ผู้ได้รับอนุมัติ") as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            raw={**self.record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"],
                 "error":"validation_failed","validator_profile":expand.VALIDATOR_PROFILE}
            fact=raw["extraction"]["facts"][0]
            fact.update(value_text=None,operator="BETWEEN",value_lower=3,value_upper=3,
                        lower_inclusive=True,upper_inclusive=None,unit="หน่วยกิต")
            changes={k:None for k in ("value_text","value_lower","value_upper","lower_inclusive","upper_inclusive")}
            changes.update(value_number=3,operator="GTE")
            self.write_review(job,raw,"source_scalar",changes)
            path=expand.OUTPUT/"cache"/(job["key"]+".json");before=path.read_bytes()
            result=expand.cached(job)
            self.assertNotIn("error",result)
            self.assertEqual(result["validation"]["facts"][0]["operator"],"GTE")
            self.assertEqual(result["source_review"]["policy_status"],"PENDING")
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(expand.cached(job),result)

    def test_source_text_defers_numeric_claim_without_deleting_fact_or_exceptions(self):
        with self.fixture((1,),content="การลงทะเบียน ไม่เกิน 50 บาท ยกเว้น ผู้ได้รับอนุมัติ") as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            raw={**self.record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"],
                 "error":"validation_failed","validator_profile":expand.VALIDATOR_PROFILE}
            raw["extraction"]["facts"][0].update(value_text=None,value_number=99,operator="EQ",unit="บาท")
            review=self.write_review(job,raw,"source_text")
            before=expand.read(expand.OUTPUT/"cache"/(job["key"]+".json"))
            result=expand.cached(job);fact=result["validation"]["facts"][0]
            self.assertEqual(fact["value_text"],job["primary"]["content"])
            self.assertIsNone(fact["value_number"])
            self.assertEqual(fact["subject_refs"],["e"])
            self.assertIn("ยกเว้น",fact["value_text"])
            self.assertEqual(result["coverage_status"],"SOURCE_TEXT_NEEDS_REVIEW")
            self.assertTrue(result["validation"]["unresolved"])
            item=expand.package(batch)["documents"][0]["extractions"][0]
            self.assertEqual(item["source_review"]["review_hash"],expand.fingerprint(review))
            self.assertEqual(item["response_hash"],expand.fingerprint(raw))
            self.assertEqual(item["coverage_status"],"SOURCE_TEXT_NEEDS_REVIEW")
            self.assertEqual(expand.read(expand.OUTPUT/"cache"/(job["key"]+".json")),before)
            stdout=io.StringIO()
            with patch.object(sys,"argv",["expand","--input",str(base),"--check"]),redirect_stdout(stdout):
                expand.main()
            self.assertIn("numeric interpretation deferred",stdout.getvalue())
            self.assertIn("PENDING",stdout.getvalue())

    def test_source_review_cannot_forge_quantities_equality_or_approve_policy(self):
        with self.fixture((1,),content="การลงทะเบียน อย่างน้อย 3 หน่วยกิต") as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            raw={**self.record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"]}
            raw["extraction"]["facts"][0].update(value_text=None,value_number=3,operator="EQ")
            valid={k:None for k in ("value_text","value_lower","value_upper","lower_inclusive","upper_inclusive")}
            valid.update(value_number=3,operator="GTE")
            self.write_review(job,raw,"source_scalar",{**valid,"operator":"LTE"})
            self.assertEqual(expand.cached(job)["error"],"validation_failed")
            for change in ({**valid,"value_number":9},{**valid,"operator":"EQ"},{**valid,"value_upper":9}):
                self.write_review(job,raw,"source_scalar",change)
                with self.assertRaises(ValueError):expand.cached(job)
            review=self.write_review(job,raw,"source_scalar",valid)
            review["policy_status"]="VERIFIED"
            expand.save(expand.OUTPUT/"reviews"/(job["key"]+".json"),review)
            with self.assertRaises(ValueError):expand.cached(job)

    def test_source_review_identity_and_actions_fail_closed(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            raw={**self.record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"]}
            for action,changes in (("remove",None),("source_text",{"value_text":"invented"})):
                self.write_review(job,raw,action,changes)
                with self.assertRaises(ValueError):expand.cached(job)
            review=self.write_review(job,raw,"source_text")
            review["edits"][0]["before_hash"]="changed"
            expand.save(expand.OUTPUT/"reviews"/(job["key"]+".json"),review)
            with self.assertRaises(ValueError):expand.cached(job)
            self.write_review(job,raw,"source_text")
            changed={**raw,"raw_response":"new provider response"}
            expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),changed)
            with self.assertRaises(ValueError):expand.cached(job)

    def test_unknown_initial_dispatch_is_reserved_across_invocations_and_repairs(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            with patch.object(expand,"call",side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):expand.extract_attempt(job,batch["schema"],None)
            self.assertEqual(expand.initial_marker(job)["status"],"RESERVED")
            pending,unresolved,ceiling=expand.extraction_plan(batch,repair_once=True)
            self.assertEqual(pending,[])
            self.assertEqual(unresolved,[job["primary"]["chunk_id"]])
            self.assertEqual(ceiling,0)
            with patch.object(expand,"call") as call:
                for repair in (None,{"error":"validation_failed"}):
                    with self.assertRaisesRegex(ValueError,"outcome unknown"):
                        expand.extract_attempt(job,batch["schema"],None,repair=repair)
                call.assert_not_called()

    def test_repair_contract_enforces_scalar_range_and_preserves_initial_identity(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            initial=expand.request_payload(job["primary"],job["contexts"],batch["schema"])
            repair=expand.request_payload(job["primary"],job["contexts"],batch["schema"],{"error":"validation_failed"})
            self.assertNotIn("anyOf",initial["response_format"]["json_schema"]["schema"]["$defs"]["Fact"])
            branches=repair["response_format"]["json_schema"]["schema"]["$defs"]["Fact"]["anyOf"]
            self.assertEqual(branches[0]["properties"]["operator"],{"const":"BETWEEN"})
            self.assertEqual(branches[1]["properties"]["lower_inclusive"],{"type":"null"})
            self.assertIn("ordinary fee",repair["messages"][0]["content"])
            self.assertIn(expand.REPAIR_PROMPT_VERSION,repair["messages"][-1]["content"])
            self.assertEqual(initial,expand.request_payload(job["primary"],job["contexts"],batch["schema"]))

    @contextmanager
    def fixture(self, counts=(1,1), content=None):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            base=root/"data/chunks/registration"
            base.mkdir(parents=True)
            data=root/"graph/data"
            (data/"inputs").mkdir(parents=True)
            (data/"inputs/schema.json").write_bytes((ROOT/"graph/data/inputs/schema.json").read_bytes())
            for i,count in enumerate(counts):
                (base/f"document{i}.json").write_text(json.dumps({"doc_id":f"source{i}","metadata":{},
                    "chunks":[{"chunk_id":f"source{i}#{n}","content":content if content is not None else f"การลงทะเบียน ต้องยืนยันในระบบ ขั้นตอน{n}","page":1}
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

    def test_openrouter_payload_and_identity_leave_frozen_pilot_unchanged(self):
        import extract
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);doc=batch["documents"][0];job=doc["jobs"][0]
            payload=expand.request_payload(job["primary"],job["contexts"],batch["schema"])
            self.assertEqual(payload["model"],"meta/muse-spark-1.3-contributor")
            self.assertEqual(payload["max_tokens"],6000)
            self.assertEqual(payload["reasoning"],{"effort":"minimal"})
            self.assertIn("value_text=null when value_number is non-null",payload["messages"][0]["content"])
            self.assertEqual(payload["provider"],{"allow_fallbacks":False,"require_parameters":True})
            self.assertEqual(extract.MODEL,"mimo-v2.6-pro")
            self.assertNotEqual(job["key"],expand.mimo_cache_key(job["primary"],job["contexts"],batch["schema"],doc["source"]))
            response=io.BytesIO(json.dumps({"id":"gen-test","usage":{"cost":0.1},"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}).encode())
            response.status=200
            with patch.object(expand,"api_key",return_value="fake-openrouter-key") as key, \
                 patch.object(expand.urllib.request,"urlopen",return_value=response) as http:
                record=expand.call(job["primary"],job["contexts"],batch["schema"])
            key.assert_called_once_with("OPENROUTER_API_KEY")
            request=http.call_args.args[0]
            self.assertEqual(request.full_url,"https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"),"Bearer fake-openrouter-key")
            self.assertEqual(json.loads(request.data)["model"],expand.MODEL)
            self.assertEqual(record["generation_id"],"gen-test")
            self.assertEqual(record["provider_cost_usd"],0.1)
            self.assertNotIn("fake-openrouter-key",json.dumps(record))

    def test_reasoning_usage_is_reported_not_guessed_and_does_not_double_count(self):
        usage={"prompt_tokens":10,"completion_tokens":20,"total_tokens":30,
               "completion_tokens_details":{"reasoning_tokens":12}}
        normalized=expand.reported_usage(usage)
        self.assertEqual(normalized,{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30,
                                     "reasoning_tokens":12,"visible_tokens":8})
        self.assertEqual(expand.reported_usage(normalized),normalized)
        for invalid in (None,True,-1,21,"12"):
            with self.subTest(value=invalid):
                self.assertNotIn("reasoning_tokens",expand.reported_usage({**usage,"completion_tokens_details":{"reasoning_tokens":invalid}}))
        with self.fixture((1,)) as (_,base),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);metrics=expand.start_metrics(batch,"smoke",1,1,0)
            expand.request_event(metrics,{"attempt_id":"a","event":"finished","api_attempted":True,
                                          "success":True,"usage":normalized})
            expand.request_event(metrics,{"attempt_id":"b","event":"finished","api_attempted":True,
                                          "success":False,"usage":{}})
            expand.finish_metrics(metrics,time.perf_counter())
            stats=expand.read(metrics["_folder"]/"stats.json")
            self.assertEqual(stats["reported_tokens"]["total_tokens"],30)
            self.assertEqual(stats["reasoning_usage"],{"reported_reasoning_tokens":12,"reported_visible_tokens":8,
                             "http_attempts_with_details":1,"http_attempts_without_details":1})

    def test_reasoning_details_survive_truncation_and_repair_unchanged(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            details=[{"type":"reasoning.encrypted","data":"opaque-test-data","format":"test","index":0}]
            body={"usage":{"completion_tokens":20,"completion_tokens_details":{"reasoning_tokens":19}},
                  "choices":[{"finish_reason":"length","message":{"content":"{","reasoning_details":details}}]}
            response=io.BytesIO(json.dumps(body).encode());response.status=200
            with patch.object(expand,"api_key",return_value="fake"),patch.object(expand.urllib.request,"urlopen",return_value=response):
                record=expand.call(job["primary"],job["contexts"],batch["schema"])
            self.assertEqual(record["error"],"incomplete_generation")
            self.assertEqual(record["usage"]["reasoning_tokens"],19)
            payload=expand.request_payload(job["primary"],job["contexts"],batch["schema"],record)
            self.assertEqual(payload["messages"][-2]["reasoning_details"],details)
            self.assertEqual(payload["max_tokens"],6000)
            self.assertEqual(payload["reasoning"],{"effort":"minimal"})

    def test_named_key_never_falls_back_to_mimo_key(self):
        with self.fixture((1,)) as (root,_),patch.object(common,"ROOT",root), \
             patch.dict(os.environ,{"MIMO_API_KEY":"fake-mimo"},clear=True):
            with self.assertRaisesRegex(RuntimeError,"OPENROUTER_API_KEY missing"):
                common.api_key("OPENROUTER_API_KEY")
            (root/".env").write_text('OPENROUTER_API_KEY="fake-router"\n')
            self.assertEqual(common.api_key("OPENROUTER_API_KEY"),"fake-router")
            self.assertEqual(common.api_key(),"fake-mimo")

    def test_general_focus_covers_text_facts_without_rewriting_historical_mimo_identity(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);doc=batch["documents"][0];job=doc["jobs"][0]
            args=(job["primary"],job["contexts"],batch["schema"],doc["source"])
            old_key=expand.mimo_cache_key(*args);new_key=expand.cache_key(*args)
            payload=expand.request_payload(*args[:3])
            focus=json.loads(payload["messages"][1]["content"])["focus"]
            self.assertIn("non-numeric",focus)
            self.assertIn("contact channels",focus)
            self.assertIn("audiences and exclusions",focus)
            self.assertIn("Never invent facts just to avoid an empty result",payload["messages"][0]["content"])
            with patch.object(expand,"FOCUS","different future focus"):
                self.assertEqual(expand.mimo_cache_key(*args),old_key)
                self.assertNotEqual(expand.cache_key(*args),new_key)

    def test_cache_revalidation_is_offline_audited_and_never_overwrites_raw_response(self):
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=AssertionError("API")):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            original={**self.record(job["primary"],job["contexts"],batch["schema"]),
                      "request_hash":job["key"],"error":"validation_failed","model":expand.MODEL}
            path=expand.OUTPUT/"cache"/(job["key"]+".json");expand.save(path,original)
            before=path.read_bytes();checked=expand.cached(job)
            self.assertNotIn("error",checked)
            self.assertEqual(checked["revalidation"]["source_record_hash"],expand.fingerprint(original))
            self.assertEqual(checked["validator_profile"],expand.VALIDATOR_PROFILE)
            self.assertEqual(checked["coverage_status"],"CANDIDATES_UNREVIEWED")
            self.assertEqual(path.read_bytes(),before)
            original["extraction"]["facts"][0]["raw_text"]="invented"
            expand.save(path,original)
            self.assertEqual(expand.cached(job)["error"],"validation_failed")

    def test_empty_cache_is_explicitly_pending_coverage_review(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            empty={"extraction":{"entities":[],"offerings":[],"facts":[],"has_tracks":[],
                                 "unresolved":["Needs scope review"]},"request_hash":job["key"]}
            expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),empty)
            self.assertEqual(expand.cached(job)["coverage_status"],"EMPTY_NEEDS_REVIEW")
            output=expand.package(batch)
            self.assertEqual(output["documents"][0]["extractions"][0]["coverage_status"],"EMPTY_NEEDS_REVIEW")

    def test_reuse_mimo_is_opt_in_validated_read_only_and_reports_mixed_origin(self):
        with self.fixture((3,)) as (_,base),redirect_stdout(io.StringIO()):
            original=expand.prepare(base);doc=original["documents"][0]
            paths=[]
            for i,job in enumerate(doc["jobs"]):
                key=expand.mimo_cache_key(job["primary"],job["contexts"],original["schema"],doc["source"])
                record={**self.record(job["primary"],job["contexts"],original["schema"]),
                        "request_hash":key,"model":expand.MIMO_MODEL}
                if i==1:
                    record["error"]="validation_failed"
                    record["extraction"]["facts"][0]["raw_text"]="fabricated"
                if i==2:record["extraction"]["facts"][0]["raw_text"]="fabricated"
                path=expand.OUTPUT/"cache"/(key+".json");expand.save(path,record)
                paths.append((path,path.read_bytes()))
                if i==1:
                    marker=expand.OUTPUT/"cache/repairs"/(key+".json")
                    expand.save(marker,{"request_hash":key,"repair_version":expand.REPAIR_VERSION,"status":"FINISHED","success":False})
                    paths.append((marker,marker.read_bytes()))
            self.assertEqual(len(expand.extraction_plan(expand.prepare(base))[0]),3)
            batch=expand.prepare(base,reuse_mimo_cache=True)
            self.assertEqual([bool(j.get("reuse_only")) for j in batch["documents"][0]["jobs"]],[True,False,False])
            self.assertEqual(len(expand.extraction_plan(batch)[0]),2)
            with patch.object(expand,"call",side_effect=self.record) as call:
                self.assertEqual(expand.extract_missing(batch,2),2)
                self.assertEqual(call.call_count,2)
            output=expand.package(batch)
            origins=output["documents"][0]["extractions"]
            self.assertEqual([r["model"] for r in origins],[expand.MIMO_MODEL,expand.MODEL,expand.MODEL])
            self.assertEqual(origins[0]["base_url"],expand.MIMO_BASE_URL)
            self.assertTrue(all(path.read_bytes()==before for path,before in paths))
            self.assertEqual(batch["batch_id"],expand.prepare(base,reuse_mimo_cache=True)["batch_id"])
            reused=batch["documents"][0]["jobs"][0]
            with patch.object(expand,"call") as call:
                with self.assertRaisesRegex(ValueError,"read-only"):
                    expand.extract_attempt(reused,batch["schema"],None)
                paths[0][0].unlink()
                with self.assertRaisesRegex(ValueError,"disappeared"):
                    expand.extract_missing(batch,2)
                call.assert_not_called()

    def test_reuse_mimo_does_not_cross_source_version_or_accept_bad_identity(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);doc=batch["documents"][0];job=doc["jobs"][0]
            key=expand.mimo_cache_key(job["primary"],job["contexts"],batch["schema"],doc["source"])
            path=expand.OUTPUT/"cache"/(key+".json")
            expand.save(path,{"request_hash":"wrong","model":expand.MIMO_MODEL})
            with self.assertRaisesRegex(ValueError,"identity mismatch"):
                expand.prepare(base,reuse_mimo_cache=True)
            expand.save(path,{**self.record(job["primary"],job["contexts"],batch["schema"]),
                              "request_hash":key,"model":expand.MIMO_MODEL})
            source_path=base/"document0.json";source=expand.read(source_path)
            source["chunks"][0]["content"]+=" เพิ่มข้อมูลใหม่"
            expand.save(source_path,source)
            changed=expand.prepare(base,reuse_mimo_cache=True)
            self.assertFalse(changed["documents"][0]["jobs"][0].get("reuse_only"))

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

    def test_offline_metrics_record_usage_failures_and_cache_without_rebilling(self):
        def measured(primary,contexts,schema):
            return {**self.record(primary,contexts,schema),"api_attempted":True,
                    "usage":{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120},"http_seconds":0.2}
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=measured) as call,redirect_stdout(io.StringIO()):
            batch=expand.prepare(base)
            first=expand.start_metrics(batch,"extract",1,1,0.1)
            expand.extract_missing(batch,1,first)
            first["status"]="SUCCEEDED"
            expand.finish_metrics(first,time.perf_counter())
            stats=expand.read(first["_folder"]/"stats.json")
            self.assertEqual(stats["confirmed_http_attempts"],1)
            self.assertEqual(stats["reported_tokens"]["total_tokens"],120)
            self.assertTrue(stats["usage_complete"])
            self.assertEqual(stats["successful_tasks"],1)
            second=expand.start_metrics(batch,"extract",0,0,0.1)
            expand.extract_missing(batch,0,second)
            second["status"]="SUCCEEDED"
            expand.finish_metrics(second,time.perf_counter())
            warm=expand.read(second["_folder"]/"stats.json")
            self.assertEqual(warm["cache_hits_at_start"],1)
            self.assertEqual(warm["confirmed_http_attempts"],0)
            self.assertNotEqual(first["_folder"],second["_folder"])
            self.assertEqual(call.call_count,1)

    def test_offline_metrics_preserve_failed_validation_usage(self):
        def invalid(primary,contexts,schema):
            record=self.record(primary,contexts,schema)
            record.update(api_attempted=True,usage={"prompt_tokens":10,"completion_tokens":2,"total_tokens":12})
            record["extraction"]["facts"][0]["raw_text"]="fabricated"
            return record
        with self.fixture((1,)) as (_,base),patch.object(expand,"call",side_effect=invalid),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);metrics=expand.start_metrics(batch,"extract",1,1,0)
            with self.assertRaises(ValueError):expand.extract_missing(batch,1,metrics)
            metrics["status"]="FAILED";expand.finish_metrics(metrics,time.perf_counter())
            stats=expand.read(metrics["_folder"]/"stats.json")
            self.assertEqual(stats["failed_tasks"],1)
            self.assertEqual(stats["reported_tokens"]["total_tokens"],12)
            self.assertEqual(stats["failures"][0]["error"],"validation_failed")
            self.assertIn("raw_text_requires_primary_evidence",stats["failures"][0]["rejected_reasons"])

    def test_call_preserves_usage_on_truncation_or_invalid_json_and_redacts_http_errors(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            for reason,raw in (("length","{}"),("stop","not JSON")):
                response=io.BytesIO(json.dumps({"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15},
                    "choices":[{"finish_reason":reason,"message":{"content":raw}}]}).encode())
                response.status=200
                with self.subTest(reason=reason),patch.object(expand,"api_key",return_value="FAKE_SECRET"), \
                     patch.object(expand.urllib.request,"urlopen",return_value=response):
                    record=expand.call(job["primary"],job["contexts"],batch["schema"])
                    self.assertEqual(record["usage"]["total_tokens"],15)
                    self.assertTrue(record["api_attempted"])
                    self.assertTrue(record["error"])
                    self.assertNotIn("FAKE_SECRET",json.dumps(record))
            error=urllib.error.HTTPError("https://example.org",402,"SECRET provider detail",{},io.BytesIO(b"SECRET"))
            with patch.object(expand,"api_key",return_value="FAKE_SECRET"), \
                 patch.object(expand.urllib.request,"urlopen",side_effect=error):
                record=expand.call(job["primary"],job["contexts"],batch["schema"])
                self.assertEqual(record["http_status"],402)
                self.assertEqual(record["usage"],{})
                self.assertNotIn("SECRET",json.dumps(record))
            with patch.object(expand,"api_key",return_value="FAKE_SECRET"), \
                 patch.object(expand.urllib.request,"urlopen",side_effect=urllib.error.URLError(OSError("SECRET transport detail"))):
                record=expand.call(job["primary"],job["contexts"],batch["schema"])
                self.assertEqual(record["transport_error_type"],"OSError")
                self.assertNotIn("SECRET",json.dumps(record))

    def test_missing_usage_is_unknown_and_interruption_leaves_durable_intent(self):
        with self.fixture((1,)) as (_,base),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);metrics=expand.start_metrics(batch,"extract",1,1,0)
            expand.request_event(metrics,{"attempt_id":"a","event":"started"})
            expand.request_event(metrics,{"attempt_id":"a","event":"finished","api_attempted":True,"success":False,"usage":{},"error":"HTTPError"})
            expand.request_event(metrics,{"attempt_id":"interrupted","event":"started"})
            expand.finish_metrics(metrics,time.perf_counter())
            stats=expand.read(metrics["_folder"]/"stats.json")
            self.assertFalse(stats["usage_complete"])
            self.assertEqual(stats["http_attempts_with_missing_usage"],1)
            self.assertEqual(stats["http_dispatch_unknown"],1)
            self.assertEqual(stats["status"],"INTERRUPTED")
            self.assertEqual(len((metrics["_folder"]/"requests.jsonl").read_text().splitlines()),3)

    def test_cli_failed_budget_still_writes_stats_without_network(self):
        with self.fixture((1,)) as (_,base),patch.object(sys,"argv",["expand.py","--input",str(base),"--extract","--max-calls","0"]), \
             patch.object(expand,"call") as call,redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):expand.main()
            call.assert_not_called()
            stats=expand.read(next((expand.OUTPUT/"batches").glob("*/offline/*/stats.json")))
            self.assertEqual(stats["status"],"FAILED")
            self.assertEqual(stats["confirmed_http_attempts"],0)

    def failed_record(self, primary, contexts, schema):
        record=self.record(primary,contexts,schema)
        record["extraction"]["facts"][0]["raw_text"]="fabricated"
        record.update(raw_response=json.dumps(record["extraction"],ensure_ascii=False),error="validation_failed")
        record["validation"]={"rejected":[{"kind":"facts","reason":"raw_text_requires_primary_evidence"}]}
        return record

    def test_repair_reuses_cached_initial_and_preserves_original_with_no_second_repair(self):
        with self.fixture((1,)) as (_,base),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            original={**self.failed_record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"]}
            expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),original)
            with patch.object(expand,"call",return_value=self.record(job["primary"],job["contexts"],batch["schema"])) as call:
                self.assertEqual(expand.extract_missing(batch,1,repair_once=True),1)
                self.assertEqual(len(call.call_args.args),4)
                self.assertEqual(call.call_args.args[3]["raw_response"],original["raw_response"])
                self.assertEqual(call.call_args.args[3]["validator_profile"],expand.VALIDATOR_PROFILE)
                marker=expand.repair_marker(job)
                self.assertEqual(expand.read(expand.OUTPUT/marker["source_cache_archive"]),original)
                self.assertEqual(expand.extract_missing(batch,0,repair_once=True),0)
                self.assertEqual(call.call_count,1)
                self.assertTrue(expand.package(batch)["documents"])

    def test_failed_repair_continues_other_jobs_but_never_exports_or_repairs_again(self):
        def response(primary,contexts,schema,repair=None):
            if primary["source_id"]=="source0":
                result=self.failed_record(primary,contexts,schema)
                result.pop("error");result.pop("validation")
                return result
            return self.record(primary,contexts,schema)
        with self.fixture((1,1)) as (_,base),patch.object(expand,"call",side_effect=response) as call,redirect_stdout(io.StringIO()):
            batch=expand.prepare(base)
            with self.assertRaisesRegex(ValueError,"still need review"):
                expand.extract_missing(batch,4,repair_once=True)
            self.assertEqual(call.call_count,3)
            first,second=[d["jobs"][0] for d in batch["documents"]]
            self.assertEqual(expand.repair_marker(first)["status"],"FINISHED")
            self.assertFalse(expand.cached(second).get("error"))
            with self.assertRaises(ValueError):expand.package(batch)
            with self.assertRaises(ValueError):expand.extract_missing(batch,0,repair_once=True)
            with self.assertRaises(ValueError):expand.extract_missing(batch,0)
            self.assertEqual(call.call_count,3)
            report=expand.read(expand.OUTPUT/"batches"/batch["batch_id"]/"needs_review.json")
            self.assertEqual(report["chunk_ids"],[first["primary"]["chunk_id"]])

    def test_interrupted_repair_reservation_prevents_duplicate_dispatch(self):
        with self.fixture((1,)) as (_,base),redirect_stdout(io.StringIO()):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            original={**self.failed_record(job["primary"],job["contexts"],batch["schema"]),"request_hash":job["key"]}
            expand.save(expand.OUTPUT/"cache"/(job["key"]+".json"),original)
            with patch.object(expand,"call",side_effect=KeyboardInterrupt) as call:
                with self.assertRaises(KeyboardInterrupt):expand.extract_missing(batch,1,repair_once=True)
                self.assertEqual(expand.repair_marker(job)["status"],"RESERVED")
                with self.assertRaises(ValueError):expand.extract_missing(batch,0,repair_once=True)
                self.assertEqual(call.call_count,1)

    def test_repair_budget_checked_upfront_and_provider_errors_stop_without_repair(self):
        with self.fixture((1,1)) as (_,base),patch.object(expand,"call",return_value={
                "api_attempted":True,"error":"HTTPError","http_status":429,"usage":{}}) as call,redirect_stdout(io.StringIO()):
            batch=expand.prepare(base)
            with self.assertRaisesRegex(ValueError,"Need 4"):
                expand.extract_missing(batch,3,repair_once=True)
            call.assert_not_called()
            with self.assertRaisesRegex(ValueError,"Extraction stopped"):
                expand.extract_missing(batch,4,repair_once=True)
            self.assertEqual(call.call_count,1)
            self.assertFalse(list((expand.OUTPUT/"cache/repairs").glob("*.json")))

    def test_repair_prompt_contains_only_original_sources_response_and_validation_feedback(self):
        with self.fixture((1,)) as (_,base):
            batch=expand.prepare(base);job=batch["documents"][0]["jobs"][0]
            failed=self.failed_record(job["primary"],job["contexts"],batch["schema"])
            payload=expand.request_payload(job["primary"],job["contexts"],batch["schema"],failed)
            self.assertEqual(payload["messages"][-2]["content"],failed["raw_response"])
            self.assertIn("raw_text_requires_primary_evidence",payload["messages"][-1]["content"])
            self.assertNotIn("gold_answer",json.dumps(payload))
            self.assertNotEqual(payload,expand.request_payload(job["primary"],job["contexts"],batch["schema"]))


if __name__ == "__main__":
    unittest.main()
