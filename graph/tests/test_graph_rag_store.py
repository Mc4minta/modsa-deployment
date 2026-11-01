"""Offline guards for the isolated Neo4j pilot adapter; never connects to a DB."""
import builtins
import contextlib
import copy
from datetime import date
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/build"))
import load_graph as store
from common import fingerprint


class GraphStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = store.prepare_import()
        cls.schema = cls.plan["schema"]
        cls.graph = store.read(store.DATA / "results/graph.json")

    def small_graph(self, range_value=False):
        state = {"review_status": "PENDING", "retrieval_enabled": False}
        text = "ทุน X รายได้ 6,501-12,500 บาท" if range_value else "ทุน X จำนวน 15 ทุน"
        fact = {"kind": "fact", "predicate": "income" if range_value else "quota", "raw_text": text,
            "value_number": None if range_value else 15, "value_text": None,
            "operator": "BETWEEN" if range_value else "EQ", "unit": None,
            "scope_text": "synthetic adapter fixture", "is_approximate": False}
        if range_value:
            fact.update(value_lower=6501, value_upper=12500, lower_inclusive=None, upper_inclusive=None)
        nodes = [
            {"id": "s", "label": "SourceDocument", "properties": {**state, "source_id": "synthetic", "title": "Fixture"}},
            {"id": "v", "label": "DocumentVersion", "properties": {**state, "version_id": "synthetic@v1", "content_hash": "a" * 64,
                "published_at": "2026-10-31", "effective_from": None, "document_status": "UNKNOWN", "verification_status": "UNVERIFIED"}},
            {"id": "c", "label": "Chunk", "properties": {**state, "chunk_id": "synthetic#0001", "content": text, "page": 1}},
            {"id": "e", "label": "Entity", "properties": {**state, "kind": "scholarship", "name": "ทุน X", "scope_text": "synthetic fixture"}},
            {"id": "f", "label": "Fact", "properties": {**state, **fact}},
        ]
        edges = [{"source": a, "type": kind, "target": b, "properties": props} for a, kind, b, props in [
            ("s", "HAS_VERSION", "v", {}), ("v", "HAS_CHUNK", "c", {}), ("e", "MENTIONED_IN", "c", {}),
            ("f", "ABOUT", "e", {}), ("f", "SUPPORTED_BY", "c", {"quote": text})]]
        return {"status": "EXPERIMENTAL_NOT_FOR_RETRIEVAL", "snapshot_hash": "synthetic-snapshot", "nodes": nodes, "edges": edges}

    def stored_tx(self, plan, content=None):
        content = copy.deepcopy(content or store.expected_content(plan))
        nodes = [{"id": key, "labels": [store.LABEL, node["label"]],
                  "props": {**node["properties"], "run_id": plan["run_id"], "node_id": key}} for key, node in content["nodes"].items()]
        edges = [{**edge, "source_run": plan["run_id"], "target_run": plan["run_id"],
                  "source_scoped": True, "target_scoped": True,
                  "props": {**edge["properties"], "edge_id": key}} for key, edge in content["edges"].items()]
        tx = Mock()
        tx.run.side_effect = lambda query, **kwargs: nodes if "MATCH (n:MODSAPilot" in query else edges
        return tx, nodes, edges

    def test_current_reviewed_export_has_full_counts_and_distinct_quote_edges(self):
        self.assertEqual(len(self.plan["nodes"]), 134)
        self.assertEqual(len(self.plan["edges"]), 231)
        triples = {(e["source"], e["type"], e["target"]) for e in self.plan["edges"].values()}
        self.assertEqual(len(triples), 224)
        self.assertEqual(sum(e["type"] == "SUPPORTED_BY" for e in self.plan["edges"].values()), 47)
        self.assertTrue(all(n["properties"]["retrieval_enabled"] is False for n in self.plan["nodes"].values()))

    def test_namespace_changes_with_reviewed_content_not_just_snapshot(self):
        original = self.small_graph()
        changed = copy.deepcopy(original)
        changed["nodes"][3]["properties"]["scope_text"] = "Another reviewed scope"
        a, b = (store.make_plan(g, self.schema) for g in (original, changed))
        self.assertEqual(a["snapshot_hash"], b["snapshot_hash"])
        self.assertNotEqual(a["graph_hash"], b["graph_hash"])
        self.assertNotEqual(a["run_id"], b["run_id"])

    def test_duplicate_dangling_or_fabricated_evidence_is_refused(self):
        for problem in ("duplicate-node", "duplicate-edge", "dangling", "quote", "unknown-label"):
            graph = self.small_graph()
            if problem == "duplicate-node":
                graph["nodes"].append(copy.deepcopy(graph["nodes"][0]))
            elif problem == "duplicate-edge":
                graph["edges"].append(copy.deepcopy(graph["edges"][0]))
            elif problem == "dangling":
                graph["edges"][-1]["target"] = "missing"
            elif problem == "quote":
                graph["edges"][-1]["properties"]["quote"] = "invented evidence"
            else:
                graph["nodes"][0]["label"] = "SourceDocument`) DELETE n //"
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                store.make_plan(graph, self.schema)

    def test_schema_identifiers_and_staging_properties_are_strict(self):
        schema = copy.deepcopy(self.schema)
        schema.pop("status")
        schema["relationship_types"].append({"label": "BAD`) DELETE n //", "description": "unsafe"})
        with self.assertRaisesRegex(ValueError, "Unsafe schema identifier"):
            store.make_plan(self.small_graph(), schema)
        for key in ("run_id", "node_id", "edge_id"):
            with self.subTest(reserved=key), self.assertRaisesRegex(ValueError, "reserved"):
                store.check_properties({key: "overwrite"}, {key: "STRING"})
        for field, value in (("value_number", True), ("value_number", float("inf")),
                             ("value_number", float("nan")), ("value_number", "15"), ("extra", "bad"),
                             ("retrieval_enabled", True), ("review_status", "APPROVED")):
            graph = self.small_graph()
            graph["nodes"][-1]["properties"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                store.make_plan(graph, self.schema)

    def test_domain_properties_cannot_override_reserved_identity_even_if_declared(self):
        for key in ("run_id", "node_id", "edge_id"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "reserved staging identity"):
                store.check_properties({key: "forged"}, {key: "STRING"})

    def test_chunk_version_and_fact_backbone_cannot_be_omitted(self):
        for missing in ("HAS_VERSION", "HAS_CHUNK", "ABOUT", "SUPPORTED_BY"):
            graph = self.small_graph()
            graph["edges"] = [e for e in graph["edges"] if e["type"] != missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                store.make_plan(graph, self.schema)

    def test_null_is_absent_but_false_and_scalar_values_are_preserved(self):
        plan = store.make_plan(self.small_graph(), self.schema)
        content = store.expected_content(plan)
        self.assertNotIn("effective_from", content["nodes"]["v"]["properties"])
        self.assertNotIn("value_text", content["nodes"]["f"]["properties"])
        self.assertIs(content["nodes"]["f"]["properties"]["retrieval_enabled"], False)
        self.assertEqual(content["nodes"]["f"]["properties"]["value_number"], 15)

    def test_expansion_metadata_lists_and_dates_survive_native_readback(self):
        from expand import expansion_schema
        schema=expansion_schema(self.schema)
        graph=self.small_graph()
        graph["nodes"][0]["properties"].update(source_uri="https://example.org/policy",topic_tags=["rules"])
        graph["nodes"][1]["properties"].update(effective_until="2026-12-31",supersedes=["synthetic@older"])
        plan=store.make_plan(graph,schema)
        content=store.expected_content(plan)
        content["nodes"]["v"]["properties"]["effective_until"]=date(2026,12,31)
        tx,_,_=self.stored_tx(plan,content)
        self.assertEqual(store.assert_run(tx,plan),fingerprint(store.expected_content(plan)))
        for invalid in ([1],"synthetic@older",[None]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                store.check_properties({"supersedes":invalid},{"supersedes":"STRING_LIST"})

    def test_synthetic_between_and_date_are_checked_locally_only(self):
        graph = self.small_graph(range_value=True)
        plan = store.make_plan(graph, self.schema)
        props = plan["nodes"]["f"]["properties"]
        self.assertEqual((props["value_lower"], props["value_upper"]), (6501, 12500))
        self.assertIsNone(props["lower_inclusive"])
        for field, value in (("value_upper", 6000), ("value_lower", "6501"), ("value_number", 6501), ("lower_inclusive", "true")):
            invalid = copy.deepcopy(graph)
            invalid["nodes"][-1]["properties"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                store.make_plan(invalid, self.schema)
        for bad in ("2569-01-01", "2026-10-31T00:00:00", "2026-1-1", True):
            invalid = copy.deepcopy(graph)
            invalid["nodes"][1]["properties"]["published_at"] = bad
            with self.subTest(date=bad), self.assertRaises(ValueError):
                store.make_plan(invalid, self.schema)

    def test_readback_compares_properties_not_only_counts(self):
        plan = store.make_plan(self.small_graph(), self.schema)
        tx, _, _ = self.stored_tx(plan)
        self.assertEqual(store.assert_run(tx, plan), fingerprint(store.expected_content(plan)))
        changed = store.expected_content(plan)
        changed["nodes"]["f"]["properties"]["value_number"] = 99
        tx, _, _ = self.stored_tx(plan, changed)
        with self.assertRaisesRegex(ValueError, "property sets differ"):
            store.assert_run(tx, plan)
        changed["nodes"]["f"]["properties"]["value_number"] = True
        tx, _, _ = self.stored_tx(plan, changed)
        with self.assertRaises(ValueError):
            store.assert_run(tx, plan)

    def test_readback_refuses_cross_run_or_unscoped_relationship_endpoints(self):
        plan = store.make_plan(self.small_graph(), self.schema)
        for field, value in (("target_run", "other-run"), ("target_scoped", False)):
            tx, _, edges = self.stored_tx(plan)
            edges[0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "cross-run"):
                store.read_run(tx, plan["run_id"])

    def test_merge_uses_parameters_distinct_edge_ids_and_native_dates(self):
        plan = store.make_plan(self.small_graph(range_value=True), self.schema)
        tx = Mock()
        calls = []

        def execute(query, **parameters):
            calls.append((query, parameters))
            count = len(parameters["rows"])
            summary = SimpleNamespace(counters=SimpleNamespace(nodes_created=count if "MERGE (n:" in query else 0,
                relationships_created=count if "MERGE (a)-" in query else 0))
            return SimpleNamespace(consume=lambda: summary)

        tx.run.side_effect = execute
        with patch.object(store, "read_run", return_value={"nodes": {}, "edges": {}}), \
             patch.object(store, "other_content", return_value={"nodes": 2, "edges": 1, "fingerprint": "unchanged"}), \
             patch.object(store, "assert_run", return_value="verified"):
            result = store.merge_run(tx, plan)
        self.assertEqual((result["nodes_created"], result["relationships_created"]), (5, 5))
        for query, parameters in calls:
            self.assertIn("run_id:$run_id", query)
            self.assertNotIn("ทุน X", query)
            self.assertEqual(parameters["run_id"], plan["run_id"])
            if "SET n:DocumentVersion" in query:
                self.assertEqual(parameters["rows"][0]["properties"]["published_at"], date(2026, 10, 31))
                self.assertNotIn("effective_from", parameters["rows"][0]["properties"])
            if "MERGE (a)-" in query:
                self.assertIn("edge_id:row.id", query)

    def test_merge_failure_on_unrelated_changes_can_trigger_managed_rollback(self):
        plan = store.make_plan(self.small_graph(), self.schema)
        summary = SimpleNamespace(counters=SimpleNamespace(nodes_created=0, relationships_created=0))
        tx = Mock()
        tx.run.return_value.consume.return_value = summary
        with patch.object(store, "read_run", return_value={"nodes": {}, "edges": {}}), \
             patch.object(store, "other_content", side_effect=[{"fingerprint": "before"}, {"fingerprint": "after"}]), \
             patch.object(store, "assert_run", return_value="verified"), \
             self.assertRaisesRegex(ValueError, "rollback"):
            store.merge_run(tx, plan)

    def probe_session(self, upper=12500):
        session, tx = Mock(), MagicMock()
        tx.__enter__.return_value = tx
        tx.__exit__.return_value = False
        session.begin_transaction.return_value = tx
        session.execute_read.side_effect = lambda callback, *args: (
            {"nodes": 134, "edges": 231, "fingerprint": "unchanged"} if callback is store.other_content else
            {"nodes": {}, "edges": {}})
        tx.run.return_value.single.return_value = {"published": SimpleNamespace(to_native=lambda: date(2026, 10, 31)),
            "lower": 6501, "upper": upper, "inclusive": None, "enabled": False}
        return session, tx

    def test_second_edition_probe_uses_same_source_identity_and_rolls_back(self):
        session, tx = self.probe_session()
        original = copy.deepcopy(self.plan)
        with patch.object(store, "merge_run") as merge, patch.object(store, "assert_run") as check:
            result = store.version_probe(session, self.plan)
        probe = merge.call_args.args[1]
        source = next(n for n in self.plan["nodes"].values() if n["label"] == "SourceDocument")
        self.assertIn(source["id"], probe["nodes"])
        self.assertEqual(probe["nodes"][source["id"]], source)
        self.assertNotEqual(probe["run_id"], self.plan["run_id"])
        self.assertNotEqual(probe["nodes"]["probe-version"]["properties"]["version_id"],
            next(n["properties"]["version_id"] for n in self.plan["nodes"].values() if n["label"] == "DocumentVersion"))
        self.assertEqual(probe["nodes"]["probe-fact"]["properties"]["operator"], "BETWEEN")
        check.assert_called_once_with(tx, self.plan)
        tx.rollback.assert_called_once_with()
        tx.commit.assert_not_called()
        self.assertEqual(result["status"], "PASSED_AND_ROLLED_BACK")
        self.assertEqual((result["probe_nodes_remaining"], result["probe_edges_remaining"]), (0, 0))
        self.assertEqual(self.plan, original)

    def test_second_edition_probe_refuses_wrong_db_range_without_committing(self):
        session, tx = self.probe_session(upper=6000)
        with patch.object(store, "merge_run"), patch.object(store, "assert_run"), \
             self.assertRaisesRegex(ValueError, "roundtrip failed"):
            store.version_probe(session, self.plan)
        tx.commit.assert_not_called()
        self.assertIs(tx.__exit__.call_args.args[0], ValueError)

    def test_offline_check_never_reads_credentials_imports_driver_or_writes(self):
        original_import = builtins.__import__

        def import_without_driver(name, *args, **kwargs):
            if name == "neo4j" or name.startswith("neo4j."):
                raise AssertionError("offline check must not import driver")
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch.object(sys, "argv", ["load_graph.py", "--check"]), \
             patch.object(store, "connection_settings", side_effect=AssertionError("no credentials")), \
             patch.object(Path, "write_text", side_effect=AssertionError("no writes")), \
             patch.object(builtins, "__import__", side_effect=import_without_driver), \
             contextlib.redirect_stdout(output):
            store.main()
        self.assertIn("134 nodes / 231 edges", output.getvalue())
        self.assertIn("no credentials, network or writes", output.getvalue())

    def test_connection_settings_are_local_only_and_do_not_read_real_env_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(store, "ROOT", Path(folder)):
            for uri in ("bolt://127.0.0.1:17687", "bolt://localhost:17687", "bolt://[::1]:17687"):
                with self.subTest(uri=uri), patch.dict(store.os.environ, {"NEO4J_AUTH": "tester/test-password", "NEO4J_URI": uri}, clear=True):
                    self.assertEqual(store.connection_settings(), (uri, "tester", "test-password", "neo4j"))
            for uri in ("bolt://production.example:17687", "bolt://127.0.0.1:7687", "neo4j://localhost:17687",
                        "bolt://user:secret@localhost:17687", "bolt://localhost:17687/path", "bolt://localhost:17687?x=y"):
                with self.subTest(uri=uri), patch.dict(store.os.environ, {"NEO4J_AUTH": "tester/test-password", "NEO4J_URI": uri}, clear=True), self.assertRaises(ValueError):
                    store.connection_settings()

    def test_live_failure_message_redacts_password_before_output(self):
        password = "TEST_PASSWORD_NOT_REAL"
        fake = SimpleNamespace(GraphDatabase=SimpleNamespace(driver=Mock(side_effect=RuntimeError("error with " + password))))
        output = io.StringIO()
        with patch.object(sys, "argv", ["load_graph.py", "--inspect"]), patch.object(store, "prepare_import", return_value=self.plan), \
             patch.object(store, "connection_settings", return_value=("bolt://127.0.0.1:17687", "tester", password, "neo4j")), \
             patch.dict(sys.modules, {"neo4j": fake}), contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
            store.main()
        self.assertNotIn(password, output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
