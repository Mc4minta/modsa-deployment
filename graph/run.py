"""Portable entrypoint for the frozen graph pilot. Run with the graph venv."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "check": [("prepare.py", "--check"), ("contracts.py", "--check"),
              ("extract.py", "--pilot", "--check"), ("load_graph.py", "--check")],
    "build": [("prepare.py",), ("contracts.py",), ("extract.py", "--offline"),
              ("load_graph.py", "--check")],
    "load": [("load_graph.py", "--load")],
    "inspect": [("load_graph.py", "--inspect")],
}


def init_neo4j(root=ROOT):
    path = root / ".graph-pilot.env"
    # Exclusive creation preserves credentials for an existing persistent database.
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing .graph-pilot.env preserved; no password change.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("NEO4J_URI=bolt://127.0.0.1:17687\nNEO4J_DATABASE=neo4j\n"
                     + "NEO4J_AUTH=neo4j/" + secrets.token_hex(20) + "\n")
    print("Created private .graph-pilot.env (password not printed). Do not commit/share this file.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in {"expand", "transfer"}:
        raise SystemExit(subprocess.run([sys.executable,str(ROOT/"graph/build"/(sys.argv[1]+".py")),*sys.argv[2:]],cwd=ROOT).returncode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(*COMMANDS, "init-neo4j", "expand", "transfer"))
    args, extra = parser.parse_known_args()
    if extra:
        parser.error("Unexpected arguments")
    if args.command == "init-neo4j":
        init_neo4j()
        return
    if not (ROOT / "data/chunks").is_dir():
        parser.error("Missing data/chunks: obtain the whole repository, not just graph/.")
    def execute(environment=None):
        for name, *options in COMMANDS[args.command]:
            print(f"Running {name} {' '.join(options)}", flush=True)
            result = subprocess.run([sys.executable, str(ROOT / "graph/build" / name), *options],
                                    cwd=ROOT, env=environment)
            if result.returncode:
                parser.exit(result.returncode, "Stopped; build outputs were not published. Inspect the error above.\n"
                            "Use graph/build/requirements.txt; for load/inspect check Neo4j connectivity.\n")
    if args.command != "build":
        execute()
        return
    # shortcut: one build writer at a time; add a lock before supporting concurrent builds.
    # Stage the complete data directory, including local caches, on the same filesystem.
    data = ROOT / "graph/data"
    with tempfile.TemporaryDirectory(prefix=".build-", dir=ROOT/"graph") as folder:
        staging = Path(folder)/"data"
        shutil.copytree(data, staging)
        execute({**os.environ, "MODSA_GRAPH_DATA_DIR": str(staging)})
        previous = Path(folder)/"previous"
        data.rename(previous)
        try:
            staging.rename(data)
        except BaseException:
            previous.rename(data)
            raise
    print("Build verified and published; previous data preserved on failed steps.")


if __name__ == "__main__":
    main()
