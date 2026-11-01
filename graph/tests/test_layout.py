"""The distributed graph build must not require the ignored research archive."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/build"))
import prepare
import load_graph


class GraphLayoutTests(unittest.TestCase):
    def test_frozen_build_and_export_still_match(self):
        bundle = prepare.build()
        self.assertEqual(bundle, prepare.read(prepare.DATA / "results/bundle.json"))
        plan = load_graph.prepare_import()
        content = load_graph.expected_content(plan)
        self.assertEqual((len(content["nodes"]), len(content["edges"])), (134, 231))

    def test_only_build_entrypoints_and_no_archive_dependency(self):
        self.assertEqual({p.name for p in (ROOT/"graph/build").glob("*.py")},
                         {"common.py","contracts.py","prepare.py","extract.py","load_graph.py","expand.py","transfer.py"})
        for path in (ROOT/"graph/build").glob("*.py"):
            self.assertNotIn(".local/graph-rag-research", path.read_text())
        self.assertEqual(prepare.DATA, ROOT/"graph/data")


if __name__ == "__main__":
    unittest.main()
