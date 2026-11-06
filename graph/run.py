"""Graph construction entrypoint; check/build/load use the general expansion pipeline."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


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
    if len(sys.argv) > 1:
        command, options = sys.argv[1], sys.argv[2:]
        if command in {"expand", "transfer", "check", "build", "load"}:
            script = "transfer" if command == "transfer" else "expand"
            if command in {"check", "build", "load"}:
                if not any(value == "--input" or value.startswith("--input=") for value in options):
                    options = ["--input", "data/chunks", *options]
                options = ["--" + command, *options]
            result = subprocess.run([sys.executable, str(ROOT/"graph/build"/(script + ".py")), *options], cwd=ROOT)
            raise SystemExit(result.returncode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "build", "load", "expand", "transfer", "init-neo4j"))
    args = parser.parse_args()
    if args.command == "init-neo4j":
        init_neo4j()


if __name__ == "__main__":
    main()
