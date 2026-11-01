import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("graph_runner", ROOT/"graph/run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GraphRunnerTests(unittest.TestCase):
    def test_expansion_help_and_arguments_are_forwarded(self):
        with patch.object(sys,"argv",["run.py","expand","--help"]), \
             patch.object(runner.subprocess,"run") as run:
            run.return_value.returncode=0
            with self.assertRaises(SystemExit) as error:
                runner.main()
            self.assertEqual(error.exception.code,0)
            self.assertEqual(run.call_args.args[0][-1],"--help")
            self.assertTrue(run.call_args.args[0][1].endswith("expand.py"))

    def test_transfer_dispatch_does_not_require_local_chunks(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runner,"ROOT",Path(folder)), \
             patch.object(sys,"argv",["run.py","transfer","check","--file","copy.json"]), \
             patch.object(runner.subprocess,"run") as run:
            run.return_value.returncode=0
            with self.assertRaises(SystemExit) as error:runner.main()
            self.assertEqual(error.exception.code,0)
            self.assertTrue(run.call_args.args[0][1].endswith("transfer.py"))
            self.assertEqual(run.call_args.args[0][2:],["check","--file","copy.json"])

    def test_init_creates_private_credentials_without_disclosure_or_overwrite(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            root = Path(folder)
            runner.init_neo4j(root)
            path = root/".graph-pilot.env"
            before = path.read_bytes()
            runner.init_neo4j(root)
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn(before.decode().split("NEO4J_AUTH=")[1].strip(), output.getvalue())
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_build_uses_same_python_no_api_and_no_database_load(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(runner,"ROOT",Path(folder)), \
             patch.object(sys,"argv",["run.py","build"]), \
             patch.object(runner.subprocess,"run") as run, contextlib.redirect_stdout(io.StringIO()):
            (Path(folder)/"data/chunks").mkdir(parents=True)
            (Path(folder)/"graph/data").mkdir(parents=True)
            run.return_value.returncode = 0
            runner.main()
        self.assertEqual(run.call_count,4)
        self.assertTrue(all(c.args[0][0] == sys.executable for c in run.call_args_list))
        arguments = [c.args[0] for c in run.call_args_list]
        self.assertTrue(any("--offline" in a for a in arguments))
        self.assertFalse(any("--extract" in a or "--load" in a for a in arguments))

    def test_failed_build_preserves_outputs_and_caches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"data/chunks").mkdir(parents=True)
            data = root/"graph/data"
            (data/"results").mkdir(parents=True)
            (data/"cache").mkdir()
            (data/"results/bundle.json").write_text("original")
            (data/"cache/saved.json").write_text("cache")

            def step(command, *, cwd, env):
                staging = Path(env["MODSA_GRAPH_DATA_DIR"])
                self.assertNotEqual(staging,data)
                (staging/"results/bundle.json").write_text("new")
                return type("Result",(),{"returncode":2})()

            with patch.object(runner,"ROOT",root), patch.object(sys,"argv",["run.py","build"]), \
                 patch.object(runner.subprocess,"run",side_effect=step), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    runner.main()
            self.assertEqual((data/"results/bundle.json").read_text(),"original")
            self.assertEqual((data/"cache/saved.json").read_text(),"cache")
            self.assertEqual(list((root/"graph").glob(".build-*")),[])

    def test_successful_build_publishes_staged_data_and_preserves_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"data/chunks").mkdir(parents=True)
            (root/"graph/data/cache").mkdir(parents=True)
            (root/"graph/data/cache/keep").write_text("keep")
            def step(command, *, cwd, env):
                (Path(env["MODSA_GRAPH_DATA_DIR"])/"new-output").write_text("new")
                return type("Result",(),{"returncode":0})()
            with patch.object(runner,"ROOT",root), patch.object(sys,"argv",["run.py","build"]), \
                 patch.object(runner.subprocess,"run",side_effect=step), contextlib.redirect_stdout(io.StringIO()):
                runner.main()
            self.assertEqual((root/"graph/data/new-output").read_text(),"new")
            self.assertEqual((root/"graph/data/cache/keep").read_text(),"keep")

    def test_failed_step_stops_pipeline(self):
        with patch.object(sys,"argv",["run.py","check"]), \
             patch.object(runner.subprocess,"run") as run, contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            run.return_value.returncode = 1
            with self.assertRaises(SystemExit):
                runner.main()
        self.assertEqual(run.call_count,1)


if __name__ == "__main__":
    unittest.main()
