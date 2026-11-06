"""CLI forwarding and private credential initialization; no legacy pilot fixtures."""
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
    def forward(self, arguments):
        with patch.object(sys,"argv",["run.py",*arguments]), patch.object(runner.subprocess,"run") as run:
            run.return_value.returncode=0
            with self.assertRaises(SystemExit) as error:
                runner.main()
            self.assertEqual(error.exception.code,0)
            return run.call_args.args[0]

    def test_expand_arguments_are_forwarded(self):
        command=self.forward(["expand","--help"])
        self.assertTrue(command[1].endswith("expand.py"))
        self.assertEqual(command[2:],["--help"])

    def test_check_defaults_to_current_chunks_without_api_or_pilot_files(self):
        command=self.forward(["check"])
        self.assertEqual(command[2:],["--check","--input","data/chunks"])

    def test_build_and_load_use_expansion_not_pilot_replay(self):
        for name in ("build","load"):
            with self.subTest(command=name):
                command=self.forward([name,"--input","data/chunks/example.json","--reuse-mimo-cache"])
                self.assertTrue(command[1].endswith("expand.py"))
                self.assertEqual(command[2:],["--"+name,"--input","data/chunks/example.json","--reuse-mimo-cache"])
                self.assertNotIn("--extract",command)

    def test_equals_style_input_is_not_replaced_by_default(self):
        command=self.forward(["check","--input=data/chunks/example.json"])
        self.assertEqual(command[2:],["--check","--input=data/chunks/example.json"])

    def test_transfer_does_not_require_source_files(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(runner,"ROOT",Path(folder)):
            command=self.forward(["transfer","check","--file","copy.json"])
            self.assertTrue(command[1].endswith("transfer.py"))
            self.assertEqual(command[2:],["check","--file","copy.json"])

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


    def test_failure_exit_code_is_preserved_without_retry(self):
        with patch.object(sys,"argv",["run.py","build"]),patch.object(runner.subprocess,"run") as run:
            run.return_value.returncode=2
            with self.assertRaises(SystemExit) as error:
                runner.main()
            self.assertEqual(error.exception.code,2)
            run.assert_called_once()

    def test_unsupported_legacy_inspect_stops_without_any_service_call(self):
        with patch.object(sys,"argv",["run.py","inspect"]),patch.object(runner.subprocess,"run") as run,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
