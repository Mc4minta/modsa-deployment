"""Offline safety checks for the small six-label extraction experiment."""
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
from extract import Evidence, apply_review, export_graph, stage, check_response_schema, selected_jobs, payload_for, JOBS
from common import fingerprint
from prepare import build
import extract as extraction_cli


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

    def test_pilot_jobs_select_only_primary_and_preserve_smoke_contexts(self):
        bundle = build()
        original = copy.deepcopy(bundle)
        jobs = selected_jobs(bundle, "pilot")
        by_id = {primary["pilot_id"]: supporting for primary, supporting in jobs}
        self.assertEqual(len(jobs), 24)
        self.assertEqual(set(by_id), {c["pilot_id"] for c in bundle["pilot"] if c["role"] == "primary"})
        self.assertTrue(all(primary["role"] == "primary" for primary, _ in jobs))
        self.assertTrue({"p24", "p26", "p27"}.isdisjoint(by_id))
        self.assertEqual({p["pilot_id"]: [c["pilot_id"] for c in contexts] for p, contexts in selected_jobs(bundle)}, JOBS)
        self.assertTrue(all([c["pilot_id"] for c in by_id[pid]] == contexts for pid, contexts in JOBS.items()))
        self.assertEqual([c["pilot_id"] for c in by_id["p05"]], ["p26", "p27"])
        self.assertEqual(bundle, original)

    def test_new_pilot_focus_uses_question_without_answers_or_gold(self):
        bundle = build()
        for question in bundle["questions"]:
            question["answer"] = "ANSWER_LEAK_SENTINEL"
            question["claims"] = [{"text": "GOLD_LEAK_SENTINEL"}]
            question["evidence_sets"] = [["EVIDENCE_LEAK_SENTINEL"]]
        primary, contexts = next(job for job in selected_jobs(bundle, "pilot") if job[0]["pilot_id"] == "p02")
        payload = payload_for(primary, contexts, bundle["schema"])
        content = payload["messages"][1]["content"]
        self.assertEqual(json.loads(content)["focus"], next(q["question"] for q in bundle["questions"] if q["id"] == "p02"))
        self.assertNotIn("LEAK_SENTINEL", content)

    def test_pilot_selection_rejects_unknown_scope_or_cross_version_context(self):
        bundle = build()
        with self.assertRaisesRegex(ValueError, "scope"):
            selected_jobs(bundle, "all")
        next(c for c in bundle["pilot"] if c["pilot_id"] == "p26")["version_id"] = "different-version"
        with self.assertRaisesRegex(ValueError, "same source version"):
            selected_jobs(bundle, "pilot")

    def saved_pilot_run(self, complete=False):
        bundle = build()
        jobs = selected_jobs(bundle, "pilot")
        hashes = {p["pilot_id"]: fingerprint({"payload": payload_for(p, c, bundle["schema"]),
                  "prompt_version": extraction_cli.PROMPT_VERSION}) for p, c in jobs}
        ids = list(hashes) if complete else list(JOBS)
        saved = {"snapshot_hash": bundle["snapshot_hash"], "records": {
            pid: {"schema_hash": fingerprint(bundle["schema"]), "cache_key": "response-" + pid} for pid in ids}}
        if complete:
            saved.update(scope="pilot", job_hashes=hashes)
        return bundle, saved

    def run_pilot_check(self, bundle, saved):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "results").mkdir()
            (root / "results/extraction.json").write_text(json.dumps(saved), encoding="utf-8")
            files = lambda: {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            before, output = files(), io.StringIO()
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(extraction_cli, "RUN", root))
                stack.enter_context(patch.object(extraction_cli, "build", return_value=bundle))
                stack.enter_context(patch.object(sys, "argv", ["extract.py", "--pilot", "--check"]))
                stack.enter_context(contextlib.redirect_stdout(output))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                forbidden = [stack.enter_context(patch.object(extraction_cli, name, side_effect=AssertionError("check must not call " + name)))
                             for name in ("api_key", "call_model", "write_reports")]
                stack.enter_context(patch.object(Path, "write_text", side_effect=AssertionError("check must not write files")))
                extraction_cli.main()
                for operation in forbidden:
                    operation.assert_not_called()
            self.assertEqual(before, files())
            return output.getvalue()

    def test_pilot_check_reuses_five_and_plans_nineteen_without_side_effects(self):
        bundle, saved = self.saved_pilot_run()
        output = self.run_pilot_check(bundle, saved)
        self.assertIn("24 primary jobs; 5 saved responses reusable; 19 initial requests pending", output)
        self.assertIn("no credentials, API, file or database writes", output)

    def test_pilot_check_reuses_complete_current_job_identities(self):
        bundle, saved = self.saved_pilot_run(complete=True)
        output = self.run_pilot_check(bundle, saved)
        self.assertIn("24 primary jobs; 24 saved responses reusable; 0 initial requests pending", output)
        self.assertIn("Pending IDs: none", output)

    def test_pilot_check_preserves_explicit_token_limit_without_api(self):
        bundle, saved = self.saved_pilot_run(complete=True)
        primary, contexts = next((p, c) for p, c in selected_jobs(bundle, "pilot") if p["pilot_id"] == "p17")
        saved["token_limits"] = {"p17": 10000}
        saved["job_hashes"]["p17"] = fingerprint({"payload": payload_for({**primary, "_max_tokens": 10000}, contexts, bundle["schema"]), "prompt_version": extraction_cli.PROMPT_VERSION})
        self.assertIn("0 initial requests pending", self.run_pilot_check(bundle, saved))
        for limit in (True, 30000, "10000"):
            saved["token_limits"] = {"p17": limit}
            with self.subTest(limit=limit), self.assertRaises(SystemExit):
                self.run_pilot_check(bundle, saved)

    def test_truncated_retry_only_calls_missing_job_and_preserves_failed_provenance(self):
        bundle, saved = self.saved_pilot_run(complete=True)
        saved["records"]["p17"].update(error="incomplete_generation", finish_reason="length")
        response = {"cache_key": "new-response", "schema_hash": fingerprint(bundle["schema"]),
            "prompt_version": extraction_cli.PROMPT_VERSION, "extraction": copy.deepcopy(self.record["extraction"])}
        staged = {"entities": [], "offerings": [], "facts": [{}], "has_tracks": [], "rejected": [], "unresolved": [], "repairs": []}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "results").mkdir()
            (root / "results/extraction.json").write_text(json.dumps(saved), encoding="utf-8")
            with patch.object(extraction_cli, "RUN", root), patch.object(extraction_cli, "INPUT", root), \
                 patch.object(extraction_cli, "build", return_value=bundle), \
                 patch.object(extraction_cli, "call_model", return_value=response) as model, \
                 patch.object(extraction_cli, "stage", return_value=staged), \
                 patch.object(extraction_cli, "export_graph", return_value={}), \
                 patch.object(extraction_cli, "write_reports") as writer, \
                 patch.object(extraction_cli, "api_key", side_effect=AssertionError("no credentials in test")), \
                 patch.object(sys, "argv", ["extract.py", "--pilot", "--extract"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                extraction_cli.main()
                model.assert_called_once()
                self.assertEqual(model.call_args.args[0]["pilot_id"], "p17")
                self.assertEqual(model.call_args.args[0]["_max_tokens"], 10000)
                self.assertEqual(writer.call_args.args[2]["p17"]["failed_attempts"][0]["finish_reason"], "length")
                self.assertEqual(writer.call_args.args[8]["token_limits"], {"p17": 10000})

    def test_pilot_check_rejects_stale_missing_or_malformed_job_identities(self):
        bundle, saved = self.saved_pilot_run(complete=True)
        _, baseline = self.saved_pilot_run()
        cases = [{**run, "job_hashes": value} for run in (saved, baseline) for value in (None, [], "not-a-mapping")]
        stale = copy.deepcopy(saved)
        stale["job_hashes"]["p02"] = "stale-hash"
        cases.append(stale)
        missing = copy.deepcopy(saved)
        missing["job_hashes"].pop("p02")
        cases.append(missing)
        for index, invalid in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(SystemExit) as error:
                self.run_pilot_check(bundle, invalid)
            self.assertEqual(error.exception.code, 2)

    def test_checked_review_ids_requires_matching_snapshot_and_response(self):
        records = {"p02": {"cache_key": "response-p02"}}
        review = {"snapshot_hash": "current", "checked_records": [{"pilot_id": "p02", "cache_key": "response-p02"}]}
        self.assertEqual(extraction_cli.checked_review_ids(review, records, "current"), {"p02"})
        with self.assertRaisesRegex(ValueError, "different snapshot"):
            extraction_cli.checked_review_ids(review, records, "changed")
        for checked in ([{"pilot_id": "p02", "cache_key": "other-response"}],
                        [{"pilot_id": "missing", "cache_key": "response-p02"}],
                        review["checked_records"] * 2):
            with self.subTest(checked=checked), self.assertRaisesRegex(ValueError, "duplicate, missing or belongs"):
                extraction_cli.checked_review_ids({**review, "checked_records": checked}, records, "current")

    def test_saved_response_schema_including_initial_attempt_is_preserved(self):
        record = {"schema_hash": fingerprint(self.schema), "initial_attempt": {"schema_hash": fingerprint(self.schema)}}
        check_response_schema({"p01": record}, self.schema)
        record["initial_attempt"]["schema_hash"] = "another-schema"
        with self.assertRaisesRegex(ValueError, "original preparation"):
            check_response_schema({"p01": record}, self.schema)

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

    def test_source_review_curates_a_copy_without_mutating_raw_response(self):
        records = {"p01": {"cache_key": "cache-1", **copy.deepcopy(self.record)}}
        original = copy.deepcopy(records)
        review = {"snapshot_hash": "snapshot-1", "edits": [
            {"pilot_id": "p01", "cache_key": "cache-1", "collection": "entities", "ref": "s",
             "changes": {"evidence": [{"chunk_id": "doc#0001", "quote": "ทุน X"}]}},
            {"pilot_id": "p01", "cache_key": "cache-1", "collection": "facts", "ref": "f", "action": "remove"}]}
        curated = apply_review(records, review, "snapshot-1")
        self.assertEqual(records, original)
        self.assertEqual(curated["p01"]["extraction"]["entities"][0]["evidence"][0]["quote"], "ทุน X")
        self.assertFalse(curated["p01"]["extraction"]["facts"])

    def test_review_can_only_remove_unsupported_offering_and_track_link(self):
        records = {"p01": {"cache_key": "cache-1", **copy.deepcopy(self.record)}}
        records["p01"]["extraction"]["offerings"] = [{"ref": "o", "scholarship_ref": "s"}]
        records["p01"]["extraction"]["has_tracks"] = [{"offering_ref": "o", "track_ref": "t"}]
        review = {"snapshot_hash": "snapshot-1", "edits": [
            {"pilot_id": "p01", "cache_key": "cache-1", "collection": "has_tracks", "ref": "o->t", "action": "remove"},
            {"pilot_id": "p01", "cache_key": "cache-1", "collection": "offerings", "ref": "o", "action": "remove"}]}
        curated = apply_review(records, review, "snapshot-1")
        self.assertFalse(curated["p01"]["extraction"]["offerings"])
        self.assertFalse(curated["p01"]["extraction"]["has_tracks"])
        self.assertTrue(records["p01"]["extraction"]["offerings"])
        review["edits"] = [{"pilot_id": "p01", "cache_key": "cache-1", "collection": "offerings", "ref": "o", "changes": {"degree": "ปริญญาตรี"}}]
        with self.assertRaisesRegex(ValueError, "only remove"):
            apply_review(records, review, "snapshot-1")

    def test_explicit_scope_review_requires_verbatim_evidence_and_unit_can_only_be_cleared(self):
        records = {"p01": {"cache_key": "cache-1", **copy.deepcopy(self.record)}}
        scope = {"pilot_id": "p01", "cache_key": "cache-1", "collection": "entities", "ref": "s", "action": "source_scope",
            "changes": {"scope_text": "ทุน X", "evidence": [{"chunk_id": "doc#0001", "quote": "ทุน X"}]}}
        unit = {"pilot_id": "p01", "cache_key": "cache-1", "collection": "facts", "ref": "f", "action": "clear_unit", "changes": {"unit": None}}
        review = {"snapshot_hash": "snapshot-1", "edits": [scope, unit]}
        curated = apply_review(records, review, "snapshot-1")
        self.assertEqual(curated["p01"]["extraction"]["entities"][0]["scope_text"], "ทุน X")
        self.assertIsNone(curated["p01"]["extraction"]["facts"][0]["unit"])
        self.assertEqual(records["p01"]["extraction"]["facts"][0]["unit"], "ทุน")
        scope["changes"]["scope_text"] = "ข้ออ้างที่ไม่ได้อยู่ในหลักฐาน"
        with self.assertRaisesRegex(ValueError, "verbatim scope"):
            apply_review(records, review, "snapshot-1")
        review["edits"] = [{**unit, "changes": {"unit": "THB"}}]
        with self.assertRaisesRegex(ValueError, "only be cleared"):
            apply_review(records, review, "snapshot-1")

    def test_source_review_requires_matching_inputs_and_forbids_value_or_scope_edits(self):
        records = {"p01": {"cache_key": "cache-1", **copy.deepcopy(self.record)}}
        edit = {"pilot_id": "p01", "cache_key": "cache-1", "collection": "facts", "ref": "f", "changes": {"kind": "fact"}}
        with self.assertRaisesRegex(ValueError, "snapshot"):
            apply_review(records, {"snapshot_hash": "different", "edits": [edit]}, "snapshot-1")
        with self.assertRaisesRegex(ValueError, "different response"):
            apply_review(records, {"snapshot_hash": "snapshot-1", "edits": [{**edit, "cache_key": "different"}]}, "snapshot-1")
        for field, value in (("value_number", 999), ("scope_text", "ปี 9999")):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "values or scope"):
                apply_review(records, {"snapshot_hash": "snapshot-1", "edits": [{**edit, "changes": {field: value}}]}, "snapshot-1")

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
