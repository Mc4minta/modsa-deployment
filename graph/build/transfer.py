"""Copy managed MODSA graphs between local Neo4j instances, without LLMs/caches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import DATA, fingerprint
from expand import document_plan, expansion_schema, load_plans, save
from load_graph import assert_run, connection_settings, make_plan, prepare_import, read

FORMAT = "modsa-graph-transfer-v1"
STATUS = "PENDING_NOT_FOR_RETRIEVAL"


def validate(package: dict) -> list[dict]:
    """Checksum detects corruption, not sender authenticity or semantic truth."""
    if not isinstance(package, dict) or set(package) != {"format", "status", "runs", "checksum"}:
        raise ValueError("Invalid graph transfer envelope")
    body = {k:v for k,v in package.items() if k != "checksum"}
    if package["format"] != FORMAT or package["status"] != STATUS or fingerprint(body) != package["checksum"]:
        raise ValueError("Unsupported transfer format/status or checksum mismatch")
    if not isinstance(package["runs"], list) or not package["runs"]:
        raise ValueError("Transfer must contain at least one graph run")
    plans, ids = [], set()
    for run in package["runs"]:
        if not isinstance(run, dict) or set(run) != {"namespace", "run_id", "schema", "graph"}:
            raise ValueError("Invalid transfer run")
        graph = run["graph"]
        if set(graph) != {"status", "snapshot_hash", "nodes", "edges"}:
            raise ValueError("Unexpected graph fields")
        if any(set(n) != {"id", "label", "properties"} for n in graph["nodes"]) or any(
                set(e) != {"source", "target", "type", "properties"} for e in graph["edges"]):
            raise ValueError("Unexpected node/edge fields")
        if run["namespace"] not in {"pilot", "expansion"}:
            raise ValueError("Unknown run namespace")
        planner = document_plan if run["namespace"] == "expansion" else make_plan
        plan = planner(graph,run["schema"])
        if run["run_id"] != plan["run_id"] or plan["run_id"] in ids:
            raise ValueError("Run identity mismatch or duplicate run")
        ids.add(plan["run_id"])
        plans.append(plan)
    return plans


def package_for_export(pilot: bool, batch_path: Path | None) -> dict:
    if pilot:
        plan = prepare_import()
        runs = [{"namespace":"pilot", "run_id":plan["run_id"], "schema":plan["schema"],
                 "graph":read(DATA/"results/graph.json")}]
    else:
        output = read(batch_path)
        schema = expansion_schema(read(DATA/"inputs/schema.json"))
        if output.get("status") != "EXPANSION_VALIDATED_PENDING_NOT_PRODUCTION" or output.get("schema_hash") != fingerprint(schema):
            raise ValueError("Batch schema/status differs from the supported expansion schema")
        runs = [{"namespace":"expansion", "run_id":d["run_id"], "schema":schema, "graph":d["graph"]}
                for d in output["documents"]]
    body = {"format":FORMAT, "status":STATUS, "runs":runs}
    package = {**body, "checksum":fingerprint(body)}
    validate(package)
    return package


def verify_database(plans: list[dict]) -> None:
    """Read-only verification: export fails if a selected run is missing/changed."""
    from neo4j import GraphDatabase, READ_ACCESS
    uri,user,password,database = connection_settings()
    with GraphDatabase.driver(uri,auth=(user,password),connection_timeout=10,max_transaction_retry_time=0) as driver:
        driver.verify_connectivity()
        with driver.session(database=database,default_access_mode=READ_ACCESS) as session:
            def verify(tx):
                for plan in plans:
                    assert_run(tx,plan)
            session.execute_read(verify)


def export(pilot: bool, batch_path: Path | None, destination: Path) -> dict:
    if destination.exists():
        raise ValueError("Destination already exists; choose a new filename, not an overwrite")
    package = package_for_export(pilot,batch_path)
    verify_database(validate(package))
    save(destination,package)
    return package


def summary(plans: list[dict]) -> str:
    return f"{len(plans)} runs / {sum(len(p['nodes']) for p in plans)} nodes / {sum(len(p['edges']) for p in plans)} edges"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command",required=True)
    sender = commands.add_parser("export",help="Read-only Neo4j verification, then write one portable JSON")
    selection = sender.add_mutually_exclusive_group(required=True)
    selection.add_argument("--pilot",action="store_true")
    selection.add_argument("--batch",type=Path,help="An expansion batch graph.json, not raw chunks")
    sender.add_argument("--out",type=Path,required=True)
    for name in ("check", "load"):
        receiver = commands.add_parser(name,help="Offline validation" if name == "check" else "Explicit Neo4j import")
        receiver.add_argument("--file",type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            package = export(args.pilot,args.batch,args.out)
            print(f"EXPORTED: {summary(validate(package))}; file {args.out}")
            print("Includes source text/quotes. Share only with authorized recipients; no credentials or LLM cache included.")
        else:
            package = read(args.file)
            plans = validate(package)
            if args.command == "check":
                print(f"CHECK OK: {summary(plans)}; no credentials, network, LLM, cache/source dependencies or writes")
            else:
                result = load_plans(plans)
                print(f"LOADED: {summary(plans)}; created {result['nodes_created']} nodes / {result['relationships_created']} edges")
                print("All nodes remain PENDING/retrieval disabled. No graph deletion or API activation.")
        print(f"Package checksum: {package['checksum']}")
    except Exception as error:
        # Never print provider/driver errors that could contain connection secrets.
        parser.exit(1,f"Transfer stopped ({type(error).__name__}); inspect package/configuration. No automatic retry or fallback.\n")


if __name__ == "__main__":
    main()
