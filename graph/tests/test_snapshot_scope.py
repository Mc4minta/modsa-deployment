import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"graph/build"))
import prepare


class SnapshotScopeTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        shutil.copytree(ROOT/"graph",root/"graph",ignore=shutil.ignore_patterns("cache","__pycache__",".build-*"))
        shutil.copytree(ROOT/"data/chunks",root/"data/chunks")
        return root

    def test_unrelated_document_does_not_change_frozen_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            original = json.loads((root/"graph/data/results/bundle.json").read_text())
            (root/"data/chunks/others/unrelated.json").write_text(json.dumps({"doc_id":"unrelated",
                "metadata":{},"chunks":[{"chunk_id":"unrelated#0001","content":"New document","page":1}]}))
            with patch.object(prepare,"ROOT",root),patch.object(prepare,"INPUT",root/"graph/data/inputs"), \
                 patch.object(prepare,"OUTPUT",root/"graph/data"):
                self.assertEqual(prepare.build(),original)

    def test_changed_source_failed_real_build_keeps_all_previous_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            data = root/"graph/data"
            before = {p.relative_to(data):p.read_bytes() for p in data.rglob("*") if p.is_file()}
            item = json.loads((data/"inputs/pilot.json").read_text())["chunks"][0]
            path = root/"data/chunks"/item["source_path"]
            source = json.loads(path.read_text())
            source["chunks"][0]["content"] += "\nChanged source for regression test"
            path.write_text(json.dumps(source,ensure_ascii=False))
            result = subprocess.run([sys.executable,str(root/"graph/run.py"),"build"],
                                    cwd=root,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("different snapshot",result.stderr)
            self.assertEqual(before,{p.relative_to(data):p.read_bytes() for p in data.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
