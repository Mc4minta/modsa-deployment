"""Connectivity diagnostics do not merge identities or change retrieval state."""
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/evaluation"))
import connectivity as audit
from langchain_core.documents import Document
from services.graph_service import PilotGraph


def fixture():
    state = {"review_status": "PENDING", "retrieval_enabled": False}
    nodes, edges, docs = {}, {}, []

    def node(key, label, **props):
        nodes[key] = {"label": label, "properties": {**state, **props}}

    def edge(a, kind, b, **props):
        edges[str(len(edges))] = {"source": a, "type": kind, "target": b, "properties": props}

    for run, chunks in (("r1", ("a", "b", "d")), ("r2", ("h",))):
        node(run + "/s", "SourceDocument", source_id=run)
        node(run + "/v", "DocumentVersion", version_id=run + "@v1", content_hash="a" * 64)
        edge(run + "/s", "HAS_VERSION", run + "/v")
        for index, chunk in enumerate(chunks):
            node(run + "/" + chunk, "Chunk", chunk_id=chunk, content=chunk)
            edge(run + "/v", "HAS_CHUNK", run + "/" + chunk)
            docs.append(Document(page_content=chunk, metadata={"source_id": run, "version_id": run + "@v1",
                "content_hash": "a" * 64, "chunk_id": chunk, "source_index": index}))
    for name, mentioned, supported in (("e1", "a", "b"), ("e2", "d", "d")):
        node("r1/" + name, "Entity", kind="scholarship", name="Same name", scope_text=name)
        node("r1/f" + name, "Fact")
        edge("r1/" + name, "MENTIONED_IN", "r1/" + mentioned)
        edge("r1/f" + name, "ABOUT", "r1/" + name)
        edge("r1/f" + name, "SUPPORTED_BY", "r1/" + supported, quote=supported)
    return PilotGraph(nodes, edges, docs, allow_pending=True), docs


class ConnectivityTests(unittest.TestCase):
    def test_uncapped_candidates_match_real_walker_without_merging_names(self):
        graph, docs = fixture()
        result = audit.candidates(graph, [docs[0]])
        self.assertEqual(list(result), ["r1/b"])
        self.assertEqual([graph.chunks[k] for k in result], graph.expand([docs[0]], limit=20)[0])
        self.assertEqual(result["r1/b"][0]["kind"], "fact_evidence")

    def test_seed_and_foreign_version_are_not_returned(self):
        graph, docs = fixture()
        self.assertEqual(audit.candidates(graph, [docs[0], docs[1]]), {})
        self.assertNotIn("r2/h", audit.candidates(graph, [docs[0]]))

    def test_same_name_split_is_hint_not_an_edge_or_approval(self):
        graph, docs = fixture()
        before = deepcopy((graph.nodes, graph.edges))
        row = {"question_id": "dev", "question": "synthetic", "answerable": True,
               "gold_chunk_ids": ["b", "d", "h"], "variants": {
                   "vector4": {"chunk_ids": ["a"]}, "graph4_plus4": {"chunk_ids": ["a", "b"]}}}
        result = audit.diagnose(graph, {"rows": [row]})
        self.assertEqual(result["summary"]["missing_reason_counts"], {
            "same_version_but_no_current_path": 1, "outside_seed_document_versions": 1})
        self.assertEqual(result["summary"]["missing_occurrences_with_exact_name_split_hint"], 1)
        self.assertEqual((graph.nodes, graph.edges), before)
        self.assertTrue(all(n["properties"]["retrieval_enabled"] is False for n in graph.nodes.values()))

    def test_components_exclude_document_hubs_and_keep_isolated_chunks(self):
        mentions, evidence = defaultdict(set, {"e": {"a"}}), defaultdict(set, {"e": {"b"}})
        components, sizes = audit.semantic_components(["a", "b", "d", "h"], mentions, evidence)
        self.assertEqual(sorted(sizes), [1, 1, 2])
        self.assertEqual(components["a"], components["b"])
        self.assertNotEqual(components["a"], components["d"])


if __name__ == "__main__":
    unittest.main()
