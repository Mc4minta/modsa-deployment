"""Only the schema is distributed as graph data; no pilot/archive dependency."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "graph/build"))
import prepare
import load_graph


class GraphLayoutTests(unittest.TestCase):
    def test_only_schema_json_is_needed_under_graph_data(self):
        paths={str(p.relative_to(ROOT/"graph/data")) for p in (ROOT/"graph/data").rglob("*.json")
               if "cache" not in p.relative_to(ROOT/"graph/data").parts}
        self.assertEqual(paths,{"inputs/schema.json"})
        prepare.check_schema(load_graph.read(ROOT/"graph/data/inputs/schema.json"))

    def test_build_modules_do_not_reference_pilot_or_archive_files(self):
        self.assertEqual({p.name for p in (ROOT/"graph/build").glob("*.py")},
                         {"common.py","contracts.py","prepare.py","extract.py","load_graph.py","expand.py","transfer.py","source_evidence.py"})
        forbidden=(".local/graph-rag-research","inputs/pilot.json","inputs/questions.json",
                   "inputs/aliases.json","results/bundle.json","results/extraction.json")
        for path in (ROOT/"graph/build").glob("*.py"):
            text=path.read_text()
            for value in forbidden:
                with self.subTest(path=path.name,dependency=value):
                    self.assertNotIn(value,text)


if __name__ == "__main__":
    unittest.main()
