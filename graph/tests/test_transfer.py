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
sys.path.insert(0,str(ROOT/"graph/build"))
import transfer
from common import fingerprint


class GraphTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=transfer.package_for_export(True,None)

    def resign(self, package):
        package["checksum"]=fingerprint({k:v for k,v in package.items() if k != "checksum"})
        return package

    def test_frozen_pilot_copy_contains_full_graph_and_no_provider_records(self):
        plans=transfer.validate(self.package)
        self.assertEqual((len(plans),len(plans[0]["nodes"]),len(plans[0]["edges"])),(1,134,231))
        self.assertEqual(set(self.package),{"format","status","runs","checksum"})
        encoded=json.dumps(self.package)
        for secret in ("MIMO_API_KEY","NEO4J_AUTH","raw_response","initial_attempt"):
            self.assertNotIn(secret,encoded)

    def test_corruption_unknown_format_and_duplicate_runs_are_refused(self):
        for problem in ("checksum","format","duplicate","run_id","unknown_field"):
            package=copy.deepcopy(self.package)
            if problem=="checksum":package["checksum"]="wrong"
            elif problem=="format":package["format"]="other"
            elif problem=="duplicate":package["runs"]*=2
            elif problem=="run_id":package["runs"][0]["run_id"]="wrong"
            else:package["credentials"]="not allowed"
            if problem != "checksum":self.resign(package)
            with self.subTest(problem=problem),self.assertRaises(ValueError):transfer.validate(package)

    def test_resigned_package_still_cannot_activate_or_inject_schema(self):
        for problem in ("active","quote","identifier"):
            package=copy.deepcopy(self.package)
            run=package["runs"][0]
            if problem=="active":run["graph"]["nodes"][0]["properties"]["retrieval_enabled"]=True
            elif problem=="quote":
                next(e for e in run["graph"]["edges"] if e["type"]=="SUPPORTED_BY")["properties"]["quote"]="fake"
            else:
                run["schema"].pop("status")
                run["schema"]["relationship_types"][0]["label"]="bad`) DELETE n //"
            with self.subTest(problem=problem),self.assertRaises(ValueError):transfer.validate(self.resign(package))

    def test_check_and_load_need_only_copy_not_sources_cache_or_api_key(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"copy.json";file.write_text(json.dumps(self.package))
            for command in ("check","load"):
                with self.subTest(command=command), \
                     patch.object(sys,"argv",["transfer.py",command,"--file",str(file)]), \
                     patch.object(transfer,"prepare_import",side_effect=AssertionError("sources")), \
                     patch.object(transfer,"package_for_export",side_effect=AssertionError("cache")), \
                     patch.object(transfer,"verify_database",side_effect=AssertionError("export verification")), \
                     patch.object(transfer,"load_plans",return_value={"nodes_created":134,"relationships_created":231}) as load, \
                     contextlib.redirect_stdout(io.StringIO()):
                    transfer.main()
                    self.assertEqual(load.call_count,1 if command=="load" else 0)

    def test_export_verifies_db_before_writing_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"copy.json"
            with patch.object(transfer,"verify_database",side_effect=ValueError("DB drift")):
                with self.assertRaises(ValueError):transfer.export(True,None,path)
                self.assertFalse(path.exists())
            with patch.object(transfer,"verify_database") as verify:
                transfer.export(True,None,path)
                verify.assert_called_once()
                self.assertEqual(transfer.validate(transfer.read(path))[0]["run_id"],self.package["runs"][0]["run_id"])
                before=path.read_bytes()
                with self.assertRaisesRegex(ValueError,"already exists"):transfer.export(True,None,path)
                self.assertEqual(path.read_bytes(),before)

    def test_bad_file_is_rejected_before_database_or_file_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"corrupt.json";path.write_text('{}')
            with patch.object(sys,"argv",["transfer.py","load","--file",str(path)]), \
                 patch.object(transfer,"load_plans") as load,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):transfer.main()
                load.assert_not_called()

    def test_expansion_copy_preserves_run_identity_and_metadata(self):
        from expand import expansion_schema,document_plan
        package=copy.deepcopy(self.package)
        run=package["runs"][0]
        run["namespace"]="expansion"
        run["schema"]=expansion_schema(run["schema"])
        source=next(n for n in run["graph"]["nodes"] if n["label"]=="SourceDocument")
        source["properties"]["source_uri"]="https://example.org/source"
        version=next(n for n in run["graph"]["nodes"] if n["label"]=="DocumentVersion")
        version["properties"].update(effective_until="2026-12-31",supersedes=["older"])
        run["run_id"]=document_plan(run["graph"],run["schema"])["run_id"]
        self.resign(package)
        plans=transfer.validate(package)
        self.assertEqual(plans[0]["run_id"],run["run_id"])
        self.assertEqual(plans[0]["nodes"][version["id"]]["properties"]["supersedes"],["older"])


if __name__=="__main__":unittest.main()
