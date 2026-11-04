"""Offline retrieval replay guards; no model, index or database access."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("retrieval_replay", ROOT / "graph/evaluation/retrieve.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class RetrievalReplayTests(unittest.TestCase):
    def fixture(self):
        docs = {str(i): Document(page_content=f"text {i}", metadata={"chunk_id": str(i), "source_id": "s"})
                for i in range(10)}
        question = {"question": "Which?", "gold_chunk_ids": ["9"]}
        saved = {"question": "Which?", "k_used": 4, "retrieved": [
            {"rank": i + 1, "chunk_id": str(i), "doc_id": "s", "content": f"text {i}"} for i in range(10)]}
        return question, saved, docs

    def test_macro_metrics_and_fixed_budget_precision(self):
        value = replay.metrics(["a", "b", "c"], ["b", "d"], 8)
        self.assertEqual(value["recall"], 0.5)
        self.assertEqual(value["precision_at_budget"], 1 / 8)
        self.assertEqual(value["reciprocal_rank"], 0.5)
        self.assertFalse(value["complete"])

    def test_no_gold_is_not_zero_recall_or_complete_success(self):
        value = replay.metrics(["a"], [], 4)
        self.assertIsNone(value["recall"])
        self.assertIsNone(value["complete"])
        self.assertIsNone(value["precision_at_budget"])

    def test_gold_does_not_select_or_reorder_seeds(self):
        question, saved, docs = self.fixture()
        before = deepcopy(saved)
        first = replay.replay_seeds(question, saved, docs)
        question.update(gold_chunk_ids=["0"], gold_answer="never select this", key_facts=["0"])
        self.assertEqual(replay.replay_seeds(question, saved, docs), first)
        self.assertEqual([d.metadata["chunk_id"] for d in first], list(map(str, range(10))))
        self.assertEqual(saved, before)

    def test_stale_content_or_wrong_source_is_rejected(self):
        for key, value in (("content", "changed"), ("doc_id", "other"), ("chunk_id", "missing")):
            question, saved, docs = self.fixture()
            saved["retrieved"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                replay.replay_seeds(question, saved, docs)

    def test_question_order_budget_and_duplicate_guards(self):
        for problem in ("question", "budget", "rank", "short", "duplicate"):
            question, saved, docs = self.fixture()
            if problem == "question":
                saved["question"] = "other"
            elif problem == "budget":
                saved["k_used"] = 8
            elif problem == "rank":
                saved["retrieved"][0]["rank"] = 2
            elif problem == "short":
                saved["retrieved"] = saved["retrieved"][:4]
            else:
                saved["retrieved"][1].update(chunk_id="0", content="text 0")
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                replay.replay_seeds(question, saved, docs)

    def test_summary_excludes_unanswerable_without_gold(self):
        rows = []
        for answerable, gold in ((True, ["a", "b"]), (False, [])):
            rows.append({"question_id": str(answerable), "answerable": answerable, "gold_chunk_ids": gold,
                         "variants": {v: {"metrics": replay.metrics(["a"], gold, 4 if v == "vector4" else 8)}
                                      for v in replay.VARIANTS}})
        summary = replay.summarize(rows)
        self.assertEqual(summary["questions"], 2)
        self.assertEqual(summary["answerable_with_gold"], 1)
        self.assertEqual(summary["variants"]["graph4_plus4"]["mean_recall"], 0.5)
        self.assertEqual(summary["graph_vs_vector4_regressed"], [])


if __name__ == "__main__":
    unittest.main()
