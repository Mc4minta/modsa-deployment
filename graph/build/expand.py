"""Build new document graphs using the frozen schema, independently of pilot QAs."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

from common import DATA, ROOT, BASE_URL, api_key, fingerprint, ssl_context
from contracts import adapt
from extract import MODEL, PROMPT_VERSION, payload_for, stage, export_graph
from load_graph import CONSTRAINT, connection_settings, make_plan, merge_run, other_content, assert_run
from prepare import check_schema

OUTPUT = ROOT / "graph/expansions"
FOCUS = ("Extract the important facts, rules, procedures, fees, dates and exceptions explicitly stated "
         "in PRIMARY. Preserve document/section/program/year/audience scope. Do not assume this is "
         "a scholarship document. If no supported semantic facts exist, return empty lists and explain "
         "the limitation in unresolved. Do not infer current policy or resolve ambiguous eligibility.")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def request_payload(primary, contexts, schema):
    return payload_for({**primary, "focus": FOCUS}, contexts, schema)


def cache_key(primary, contexts, schema, source):
    return fingerprint({"payload":request_payload(primary, contexts, schema), "source":source,
                        "prompt_version":PROMPT_VERSION, "expansion_version":"generic-v1"})


def expansion_schema(base):
    """Add metadata properties without rewriting the historical frozen pilot."""
    check_schema(base)
    schema = copy.deepcopy(base)
    schema["schema_version"] += "+source-metadata-v1"
    additions = {"SourceDocument": {"source_uri":"STRING", "topic_tags":"STRING_LIST", "content_type":"STRING"},
                 "DocumentVersion": {"effective_until":"DATE", "ingested_at":"DATE", "supersedes":"STRING_LIST"}}
    for node in schema["node_types"]:
        existing = {p["name"]:p["type"] for p in node["properties"]}
        for name, kind in additions.get(node["label"], {}).items():
            if name in existing and existing[name] != kind:
                raise ValueError("Incompatible expansion metadata property")
            if name not in existing:
                node["properties"].append({"name":name,"type":kind})
    schema["fingerprint"] = fingerprint({k:v for k,v in schema.items() if k != "fingerprint"})
    check_schema(schema)
    return schema


def prepare(input_path):
    """A file/directory is a selection of whole document versions, not pilot IDs."""
    base = (ROOT / "data/chunks").resolve()
    path = Path(input_path).resolve()
    if not path.is_relative_to(base) or not path.exists():
        raise ValueError("--input must be an existing JSON file/directory under data/chunks")
    paths = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    if not paths:
        raise ValueError("No chunk JSON files selected")
    schema = expansion_schema(read(DATA / "inputs/schema.json"))
    documents, source_ids, chunk_ids = [], set(), set()
    for file in paths:
        if file.suffix != ".json" or not file.resolve().is_relative_to(base):
            raise ValueError("Unsupported file or symlink outside data/chunks")
        record, _ = adapt(file, read(file), {})
        source_id = record["source"]["source_id"]
        if source_id in source_ids or not record["chunks"]:
            raise ValueError("Duplicate source_id or document without chunks")
        source_ids.add(source_id)
        source = {**record["source"], **record["version"], "source_path":record["source_path"]}
        chunks = []
        for index, chunk in enumerate(record["chunks"]):
            cid = chunk["legacy_chunk_id"]
            if cid in chunk_ids:
                raise ValueError("Duplicate chunk_id in selected input")
            chunk_ids.add(cid)
            # The reused validator calls this field pilot_id; here it is a generated job ID, not a pilot selection.
            chunks.append({"pilot_id":fingerprint([source["version_id"],cid]), "chunk_id":cid,
                "source_id":source_id,"version_id":source["version_id"],"source_index":index,
                "category":file.parent.name,"page":chunk["page"],"content":chunk["content"],"role":"primary"})
        jobs = []
        for index, primary in enumerate(chunks):
            # shortcut: first chunk + immediate neighbours; section-aware context needs separate evaluation.
            indices = sorted({0, index-1, index+1} - {index, -1, len(chunks)})
            context = [chunks[i] for i in indices]
            key = cache_key(primary, context, schema, source)
            jobs.append({"primary":primary,"contexts":context,"key":key})
        documents.append({"source":source,"jobs":jobs})
    batch_id = fingerprint({"schema":schema,"documents":[
        {"source":d["source"],"requests":[j["key"] for j in d["jobs"]]} for d in documents]})
    return {"batch_id":batch_id,"schema":schema,"documents":documents}


def cached(job):
    path = OUTPUT/"cache"/(job["key"]+".json")
    if not path.exists():
        return None
    record = read(path)
    if record.get("request_hash") != job["key"]:
        raise ValueError(f"Cache identity mismatch for {job['key']}; refusing API fallback")
    return record


def call(primary, contexts, schema):
    """One HTTP request, no model repair/provider fallback or automatic retry."""
    key = api_key()
    request = urllib.request.Request(BASE_URL+"/chat/completions",
        data=json.dumps(request_payload(primary, contexts, schema)).encode(),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,context=ssl_context(),timeout=150) as response:
        choice = json.load(response)["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Incomplete model response")
    raw = choice["message"].get("content") or ""
    return {"model":MODEL,"raw_response":raw,"extraction":json.loads(raw)}


def extract_missing(batch, max_calls):
    pending = []
    for document in batch["documents"]:
        for job in document["jobs"]:
            record = cached(job)
            if record is None or record.get("error"):
                pending.append(job)
    if max_calls < len(pending):
        raise ValueError(f"Need {len(pending)} requests; --max-calls budget is {max_calls}. Select fewer documents or raise the explicit budget")
    calls = 0
    for job in pending:
        calls += 1
        try:
            record = call(job["primary"],job["contexts"],batch["schema"])
            validation = stage(job["primary"],job["contexts"],record,batch["schema"])
            record["validation"] = validation
            if validation["rejected"]:
                record["error"] = "validation_failed"
        except urllib.error.HTTPError as error:
            record = {"error":"HTTPError", "http_status":error.code}
        except Exception as error:
            # Provider error bodies can contain secrets; never persist or print them.
            record = {"error":type(error).__name__}
        record["request_hash"] = job["key"]
        save(OUTPUT/"cache"/(job["key"]+".json"),record)
        print(f"EXTRACT {calls}/{len(pending)}",flush=True)
        if record.get("error"):
            raise ValueError(f"Extraction stopped; inspect cache {job['key']}; successful caches preserved")
    return calls


def package(batch):
    documents = []
    for document in batch["documents"]:
        staged, jobs = {}, []
        for job in document["jobs"]:
            record = cached(job)
            if record is None or record.get("error"):
                raise ValueError(f"Missing/failed extraction for {job['primary']['chunk_id']} (cache {job['key']}); use --check then explicitly budget --extract")
            result = stage(job["primary"],job["contexts"],record,batch["schema"])
            if result["rejected"]:
                raise ValueError(f"Evidence validation failed for {job['primary']['chunk_id']} (cache {job['key']}); no export published")
            staged[job["primary"]["pilot_id"]] = result
            jobs.append((job["primary"],job["contexts"]))
        bundle = {"snapshot_hash":fingerprint({"source":document["source"],"keys":[j["key"] for j in document["jobs"]]}),
                  "schema":batch["schema"],"sources":[document["source"]]}
        graph = export_graph(bundle,jobs,staged)
        plan = document_plan(graph,batch["schema"])
        documents.append({"source":document["source"],"graph":graph,"run_id":plan["run_id"],
            "unresolved":[{"chunk_id":j["primary"]["chunk_id"],"notes":staged[j["primary"]["pilot_id"]]["unresolved"]} for j in document["jobs"]]})
    return {"status":"EXPANSION_VALIDATED_PENDING_NOT_PRODUCTION","batch_id":batch["batch_id"],
            "schema_hash":fingerprint(batch["schema"]),"documents":documents}


def document_plan(graph, schema):
    plan = make_plan(graph,schema)
    plan["run_id"] = "modsa-expansion-v1:"+fingerprint({"graph_hash":plan["graph_hash"],"schema_hash":plan["schema_hash"]})
    return plan


def merge_batch(tx, plans):
    run_ids = [p["run_id"] for p in plans]
    before = other_content(tx,run_ids)
    first = [merge_run(tx,plan,check_unrelated=False) for plan in plans]
    second = [merge_run(tx,plan,check_unrelated=False) for plan in plans]
    if any(r["nodes_created"] or r["relationships_created"] for r in second):
        raise ValueError("Idempotency check failed; rollback batch")
    if any(a["content_hash"] != b["content_hash"] for a,b in zip(first,second)):
        raise ValueError("Readback changed; rollback batch")
    # Recheck the final state too: later imports must not alter earlier document runs.
    for plan in plans:
        assert_run(tx,plan)
    if before != other_content(tx,run_ids):
        raise ValueError("Unrelated graph changed; rollback batch")
    return {"documents":len(plans),"nodes_created":sum(r["nodes_created"] for r in first),
            "relationships_created":sum(r["relationships_created"] for r in first)}


def load(batch, output):
    return load_plans([document_plan(d["graph"],batch["schema"]) for d in output["documents"]])


def load_plans(plans):
    """Import already validated plans in one transaction, including portable copies."""
    from neo4j import GraphDatabase
    uri,user,password,database = connection_settings()
    with GraphDatabase.driver(uri,auth=(user,password),connection_timeout=10,max_transaction_retry_time=0) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            session.run(CONSTRAINT).consume()
            constraints = list(session.run("SHOW CONSTRAINTS YIELD type, labelsOrTypes, properties RETURN type, labelsOrTypes, properties"))
            if not any("UNIQUENESS" in row["type"] and row["labelsOrTypes"] == ["MODSAPilot"]
                       and row["properties"] == ["run_id","node_id"] for row in constraints):
                raise ValueError("Required run identity constraint is missing")
            # All document imports and readback checks share one transaction.
            return session.execute_write(merge_batch,plans)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,help="Whole document JSON file/directory under data/chunks")
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("check","extract","build","load"):
        mode.add_argument("--"+flag,action="store_true")
    parser.add_argument("--max-calls",type=int,default=0)
    args = parser.parse_args()
    try:
        if args.max_calls < 0 or (args.max_calls and not args.extract):
            raise ValueError("--max-calls applies only to --extract and must be nonnegative")
        batch = prepare(args.input)
        jobs = [j for d in batch["documents"] for j in d["jobs"]]
        missing = sum((r is None or bool(r.get("error"))) for r in (cached(j) for j in jobs))
        print(f"PLAN: {len(batch['documents'])} documents / {len(jobs)} chunks / {missing} missing requests; model {MODEL}")
        if args.check:
            print("Check only: no credentials, API, file writes or database operations")
            return
        if args.extract:
            calls = extract_missing(batch,args.max_calls)
            print(f"New API calls: {calls}")
        output = package(batch)
        path = OUTPUT/"batches"/batch["batch_id"]/"graph.json"
        if args.load:
            if not path.exists() or read(path) != output:
                raise ValueError("Build/current-source mismatch; build and inspect this batch before loading")
            result = load(batch,output)
            save(path.parent/"load.json",{"batch_id":batch["batch_id"],"run_ids":[d["run_id"] for d in output["documents"]],**result})
            print(f"LOADED: {result['documents']} document versions; {result['nodes_created']} new nodes / {result['relationships_created']} new edges")
        else:
            save(path,output)
            lines = ["# Expansion batch", "", f"Batch: `{batch['batch_id']}`", "",
                "Evidence validation passed; semantic correctness/current policy is NOT approved. All nodes remain PENDING with retrieval disabled.", "",
                "| Source | Version | Nodes | Edges | Facts | Unresolved notes |", "| --- | --- | ---: | ---: | ---: | ---: |"]
            for doc in output["documents"]:
                graph = doc["graph"]
                lines.append(f"| {doc['source']['source_id'].replace('|',' ')} | {doc['source']['version_id'].replace('|',' ')} | {len(graph['nodes'])} | {len(graph['edges'])} | {sum(n['label']=='Fact' for n in graph['nodes'])} | {sum(len(r['notes']) for r in doc['unresolved'])} |")
            lines.extend(["", "See graph.json for source quotes, unresolved notes and exact run IDs. No records are silently marked ACTIVE/VERIFIED.", ""])
            (path.parent/"README.md").write_text("\n".join(lines),encoding="utf-8")
            print(f"BUILT: {path.relative_to(ROOT)}; pending only, no DB writes")
    except Exception as error:
        parser.exit(1,f"Expansion stopped ({type(error).__name__}); no automatic retry/provider fallback. "
                    +(str(error)+"\n" if type(error) is ValueError else "Inspect input/configuration; secrets omitted.\n"))


if __name__ == "__main__":
    main()
