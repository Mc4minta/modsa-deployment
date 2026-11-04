"""Optional offline lexical experiment; no API, embedding service or database."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/evaluation"))
try:
    import direct_search as search
except ModuleNotFoundError as error:
    if error.name == "sklearn" or error.name.startswith("sklearn."):
        raise unittest.SkipTest("Optional experiment needs graph/evaluation/requirements.txt") from error
    raise
from test_graph_connectivity import fixture


class DirectGraphSearchTests(unittest.TestCase):
    def index(self):
        graph, docs = fixture()
        graph.nodes["r1/fe1"]["properties"].update(raw_text="registration permission blue")
        graph.nodes["r1/fe2"]["properties"].update(raw_text="emergency scholarship green")
        return graph, docs, search.LexicalIndex(graph, search.fact_records(graph))

    def test_query_can_enter_fact_without_path_from_vector_seed(self):
        graph, docs, index = self.index()
        self.assertEqual([d.metadata["chunk_id"] for d in graph.expand([docs[0]], limit=4)[0]], ["b"])
        found, trace = index.search("emergency", [docs[0]])
        self.assertEqual([d.metadata["chunk_id"] for d in found], ["d"])
        self.assertEqual(trace[0]["record_id"], "r1/fe2")
        support = graph.edges[trace[0]["support_edge_id"]]
        self.assertEqual(support["type"], "SUPPORTED_BY")
        self.assertEqual(support["target"], trace[0]["chunk_node_id"])
        self.assertIn(trace[0]["quote"], found[0].page_content)

    def test_no_match_and_seed_only_match_return_empty(self):
        _, docs, index = self.index()
        self.assertEqual(index.search("ZZZZ999999", [docs[0]]), ([], []))
        self.assertEqual(index.search("emergency", [docs[2]]), ([], []))
        self.assertEqual(index.search("", [docs[0]]), ([], []))
        self.assertEqual(index.search("emergency", [docs[0]], limit=0), ([], []))

    def test_multiple_records_for_one_chunk_do_not_duplicate_context(self):
        graph, docs, _ = self.index()
        records = search.fact_records(graph)
        duplicate = deepcopy(records[1])
        duplicate["record_id"] = "another-record"
        index = search.LexicalIndex(graph, records + [duplicate])
        found, trace = index.search("emergency", [docs[0]])
        self.assertEqual(len(found), 1)
        self.assertEqual(len(trace), 1)

    def test_search_is_deterministic_and_does_not_mutate_graph_or_seeds(self):
        graph, docs, index = self.index()
        before = deepcopy((graph.nodes, graph.edges, docs))
        first = index.search("same name", [docs[0]])
        self.assertEqual(index.search("same name", [docs[0]]), first)
        self.assertEqual((graph.nodes, graph.edges, docs), before)
        self.assertTrue(all(n["properties"]["retrieval_enabled"] is False for n in graph.nodes.values()))

    def test_invalid_input_and_stale_seed_fail_closed(self):
        _, docs, index = self.index()
        for limit in (-1, True, 1.5, 21):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                index.search("same name", docs[:1], limit=limit)
        stale = deepcopy(docs[0])
        stale.page_content = "changed"
        with self.assertRaises(ValueError):
            index.search("same name", [stale])
        with self.assertRaises(ValueError):
            index.search({"question": "same name", "gold_chunk_ids": ["d"]}, docs[:1])

    def test_facts_without_evidence_are_not_indexed(self):
        graph, _, _ = self.index()
        graph.outgoing["r1/fe1"] = [(key, edge) for key, edge in graph.outgoing["r1/fe1"]
                                     if edge["type"] != "SUPPORTED_BY"]
        with self.assertRaises(ValueError):
            search.fact_records(graph)

    def test_text_normalization_does_not_remove_year_or_negation(self):
        self.assertEqual(search.normalize("  NOT\nEligible ๒๕๖๙ "), "not eligible ๒๕๖๙")


if __name__ == "__main__":
    unittest.main()
