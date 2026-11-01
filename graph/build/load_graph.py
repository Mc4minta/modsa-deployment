"""Load only the reviewed pilot into a content-addressed local Neo4j namespace.

--check is offline; --inspect only reads Neo4j; --load imports twice and verifies.
No LLM, Chroma, policy activation, deletion or cross-run entity merging.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
import math
import os
import re
from urllib.parse import urlsplit

from common import DATA, ROOT, fingerprint
from contracts import NumericRange
from extract import JOBS, apply_review, checked_review_ids, export_graph, selected_jobs, stage
from prepare import build, check_schema, extraction_status

LABEL = "MODSAPilot"
CONSTRAINT = "CREATE CONSTRAINT modsa_pilot_identity IF NOT EXISTS FOR (n:MODSAPilot) REQUIRE (n.run_id, n.node_id) IS UNIQUE"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_properties(properties: dict, declared: dict) -> None:
    if not isinstance(properties, dict) or not properties.keys() <= declared.keys():
        raise ValueError("Graph contains undeclared properties")
    if properties.keys() & {"run_id", "node_id", "edge_id"}:
        raise ValueError("Domain properties cannot overwrite reserved staging identity")
    for key, value in properties.items():
        if value is None:
            continue
        kind = declared[key]
        valid = {"STRING": type(value) is str, "INTEGER": type(value) is int,
                 "FLOAT": type(value) in (int, float) and math.isfinite(value),
                 "BOOLEAN": type(value) is bool, "DATE": type(value) is str,
                 "STRING_LIST": type(value) is list and all(type(v) is str for v in value)}.get(kind, False)
        if not valid:
            raise ValueError(f"Invalid {kind} property: {key}")
        if kind == "DATE" and (date.fromisoformat(value).isoformat() != value or date.fromisoformat(value).year > 2400):
            raise ValueError("Dates must be explicit Gregorian ISO dates")


def make_plan(graph: dict, schema: dict) -> dict:
    check_schema(schema)
    if graph.get("status") != "EXPERIMENTAL_NOT_FOR_RETRIEVAL" or not graph.get("nodes"):
        raise ValueError("Only a nonempty experimental graph may be staged")
    declarations = {}
    for collection in ("node_types", "relationship_types"):
        declarations[collection] = {}
        for record in schema[collection]:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", record["label"]):
                raise ValueError("Unsafe schema identifier")
            declarations[collection][record["label"]] = {p["name"]: p["type"] for p in record.get("properties", [])}
    nodes, edges = {}, {}
    for node in graph["nodes"]:
        if not isinstance(node["id"], str) or not node["id"] or node["id"] in nodes or node["label"] not in declarations["node_types"]:
            raise ValueError("Duplicate, empty or unknown graph node")
        props = node["properties"]
        check_properties(props, declarations["node_types"][node["label"]])
        if props.get("review_status") != "PENDING" or props.get("retrieval_enabled") is not False:
            raise ValueError("Staging must not activate retrieval")
        if node["label"] == "Fact":
            range_fields = ("value_lower", "value_upper", "lower_inclusive", "upper_inclusive")
            if props.get("operator") == "BETWEEN":
                NumericRange(lower=props.get("value_lower"), upper=props.get("value_upper"),
                    lower_inclusive=props.get("lower_inclusive"), upper_inclusive=props.get("upper_inclusive"))
                if props.get("value_number") is not None or props.get("value_text") is not None:
                    raise ValueError("Range cannot also contain a scalar or text value")
            elif any(props.get(k) is not None for k in range_fields):
                raise ValueError("Range fields require BETWEEN")
        nodes[node["id"]] = node
    patterns = {tuple(p) for p in schema["patterns"]}
    by_type = defaultdict(list)
    for edge in graph["edges"]:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise ValueError("Dangling graph relationship")
        if (nodes[edge["source"]]["label"], edge["type"], nodes[edge["target"]]["label"]) not in patterns:
            raise ValueError("Relationship outside schema")
        check_properties(edge["properties"], declarations["relationship_types"][edge["type"]])
        identity = fingerprint(edge)
        if identity in edges:
            raise ValueError("Duplicate graph relationship")
        if edge["type"] == "SUPPORTED_BY":
            quote = edge["properties"].get("quote")
            if not quote or quote not in nodes[edge["target"]]["properties"]["content"]:
                raise ValueError("Evidence quote does not match its source chunk")
        edges[identity] = edge
        by_type[edge["type"]].append(edge)
    for node_id, node in nodes.items():
        label = node["label"]
        if label == "Fact" and (not any(e["source"] == node_id for e in by_type["ABOUT"]) or not any(e["source"] == node_id for e in by_type["SUPPORTED_BY"])):
            raise ValueError("Fact requires a subject and source evidence")
        if label in {"Chunk", "DocumentVersion"}:
            relation = "HAS_CHUNK" if label == "Chunk" else "HAS_VERSION"
            if sum(e["target"] == node_id for e in by_type[relation]) != 1:
                raise ValueError("Each chunk/version requires exactly one parent")
    graph_hash = fingerprint(graph)
    run_id = schema["schema_version"] + ":" + fingerprint({"graph_hash": graph_hash, "schema_hash": fingerprint(schema)})
    return {"run_id": run_id, "graph_hash": graph_hash, "snapshot_hash": graph["snapshot_hash"],
        "schema_hash": fingerprint(schema), "schema_version": schema["schema_version"], "schema": schema,
        "nodes": nodes, "edges": edges, "declarations": declarations}


def prepare_import() -> dict:
    bundle = build()
    saved, graph = read(DATA / "results/extraction.json"), read(DATA / "results/graph.json")
    if saved.get("scope") != "pilot" or not extraction_status(bundle, saved, graph)["ready"]:
        raise ValueError("Complete pilot source review is required before staging")
    review, pilot_review = read(DATA / "inputs/smoke_review.json"), read(DATA / "inputs/pilot_review.json")
    checked = set(JOBS) | checked_review_ids(pilot_review, saved["records"], bundle["snapshot_hash"])
    if sorted(checked) != saved["source_checked_ids"] or review != saved["review"] or pilot_review != saved["pilot_review"]:
        raise ValueError("Source review changed; replay extraction offline before staging")
    curated = apply_review(saved["records"], review, saved.get("review_snapshot_hash", bundle["snapshot_hash"]))
    curated = apply_review(curated, pilot_review, bundle["snapshot_hash"])
    jobs = selected_jobs(bundle, "pilot")
    staged = {p["pilot_id"]: stage(p, c, curated[p["pilot_id"]], bundle["schema"]) for p, c in jobs}
    if any(s["rejected"] or not s["facts"] for s in staged.values()) or staged != saved["staged"] or export_graph(bundle, jobs, staged) != graph:
        raise ValueError("Graph/source validation drift; replay and review before staging")
    return make_plan(graph, bundle["schema"])


def connection_settings() -> tuple[str, str, str, str]:
    values = {}
    path = ROOT / ".graph-pilot.env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and key.startswith("NEO4J_"):
                values[key] = value.strip().strip("\"'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("NEO4J_")})
    uri, database = values.get("NEO4J_URI", "bolt://127.0.0.1:17687"), values.get("NEO4J_DATABASE", "neo4j")
    parsed = urlsplit(uri)
    # shortcut: local pilot only; configure deployment separately before allowing remote databases.
    if parsed.scheme != "bolt" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.port != 17687 or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Only the isolated loopback Bolt endpoint on port 17687 is allowed")
    user, sep, password = values.get("NEO4J_AUTH", "").partition("/")
    user, password = values.get("NEO4J_USER", user), values.get("NEO4J_PASSWORD", password)
    if not user or not password or not re.fullmatch(r"[a-zA-Z0-9_.-]+", database):
        raise ValueError("Local Neo4j credentials/database are missing or invalid")
    return uri, user, password, database


def json_value(value):
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise ValueError("Unsupported database property type")


def expected_content(plan: dict) -> dict:
    clean = lambda props: {k: v for k, v in props.items() if v is not None}
    return {"nodes": {key: {"label": n["label"], "properties": clean(n["properties"])} for key, n in plan["nodes"].items()},
        "edges": {key: {**e, "properties": clean(e["properties"])} for key, e in plan["edges"].items()}}


def read_run(tx, run_id: str) -> dict:
    nodes, edges = {}, {}
    for row in tx.run("MATCH (n:MODSAPilot {run_id:$run_id}) RETURN properties(n)['node_id'] AS id, labels(n) AS labels, properties(n) AS props", run_id=run_id):
        labels, props = set(row["labels"]) - {LABEL}, dict(row["props"])
        if len(labels) != 1 or not row["id"] or row["id"] in nodes:
            raise ValueError("Stored run contains duplicate or unrecognized nodes")
        props.pop("run_id"); props.pop("node_id")
        nodes[row["id"]] = {"label": labels.pop(), "properties": json_value(props)}
    query = """MATCH (a)-[r]->(b)
        WHERE (a:MODSAPilot AND a.run_id=$run_id) OR (b:MODSAPilot AND b.run_id=$run_id)
        RETURN properties(a)['node_id'] AS source, properties(b)['node_id'] AS target, a.run_id AS source_run, b.run_id AS target_run,
               a:MODSAPilot AS source_scoped, b:MODSAPilot AS target_scoped,
               type(r) AS type, properties(r) AS props"""
    for row in tx.run(query, run_id=run_id):
        props = dict(row["props"])
        key = props.pop("edge_id", None)
        if not key or key in edges or not row["source_scoped"] or not row["target_scoped"] or row["source_run"] != run_id or row["target_run"] != run_id or row["source"] not in nodes or row["target"] not in nodes:
            raise ValueError("Stored run has duplicate, dangling or cross-run evidence")
        edges[key] = {"source": row["source"], "target": row["target"], "type": row["type"], "properties": json_value(props)}
    return {"nodes": nodes, "edges": edges}


def assert_run(tx, plan: dict) -> str:
    content = read_run(tx, plan["run_id"])
    if fingerprint(content) != fingerprint(expected_content(plan)):
        raise ValueError("Stored node/edge/property sets differ from the reviewed export")
    return fingerprint(content)


def other_content(tx, run_id: str | list[str]) -> dict:
    run_ids = [run_id] if isinstance(run_id, str) else run_id
    nodes = [json_value(dict(r)) for r in tx.run("MATCH (n) WHERE NOT (n:MODSAPilot AND coalesce(n.run_id IN $run_ids,false)) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props ORDER BY id", run_ids=run_ids)]
    for node in nodes:
        node["labels"].sort()
    edges = [json_value(dict(r)) for r in tx.run("MATCH (a)-[r]->(b) WHERE NOT (a:MODSAPilot AND coalesce(a.run_id IN $run_ids,false) AND b:MODSAPilot AND coalesce(b.run_id IN $run_ids,false)) RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type, properties(r) AS props ORDER BY id", run_ids=run_ids)]
    return {"nodes": len(nodes), "edges": len(edges), "fingerprint": fingerprint({"nodes": nodes, "edges": edges})}


def merge_run(tx, plan: dict, *, check_unrelated: bool = True) -> dict:
    existing = read_run(tx, plan["run_id"])
    if existing["nodes"] or existing["edges"]:
        assert_run(tx, plan)
    before = other_content(tx, plan["run_id"]) if check_unrelated else None
    counters = {"nodes_created": 0, "relationships_created": 0}
    groups = defaultdict(list)
    for node in plan["nodes"].values():
        declared = plan["declarations"]["node_types"][node["label"]]
        props = {k: date.fromisoformat(v) if declared[k] == "DATE" else v for k, v in node["properties"].items() if v is not None}
        groups[node["label"]].append({"id": node["id"], "properties": props})
    for label, rows in groups.items():
        query = f"UNWIND $rows AS row MERGE (n:MODSAPilot {{run_id:$run_id, node_id:row.id}}) SET n:{label} SET n += row.properties"
        summary = tx.run(query, run_id=plan["run_id"], rows=rows).consume()
        counters["nodes_created"] += summary.counters.nodes_created
    groups.clear()
    for key, edge in plan["edges"].items():
        groups[edge["type"]].append({**edge, "id": key, "properties": {k: v for k, v in edge["properties"].items() if v is not None}})
    for relation, rows in groups.items():
        query = f"""UNWIND $rows AS row MATCH (a:MODSAPilot {{run_id:$run_id,node_id:row.source}})
            MATCH (b:MODSAPilot {{run_id:$run_id,node_id:row.target}})
            MERGE (a)-[r:{relation} {{edge_id:row.id}}]->(b) SET r += row.properties"""
        summary = tx.run(query, run_id=plan["run_id"], rows=rows).consume()
        counters["relationships_created"] += summary.counters.relationships_created
    content_hash = assert_run(tx, plan)
    if check_unrelated and before != other_content(tx, plan["run_id"]):
        raise ValueError("Unrelated graph changed; rollback pilot import")
    return {**counters, "content_hash": content_hash, "unrelated_graph": before}


def version_probe(session, current: dict) -> dict:
    """Exercise a second edition with the same source identity, then rollback."""
    state = {"review_status": "PENDING", "retrieval_enabled": False}
    source = next(n for n in current["nodes"].values() if n["label"] == "SourceDocument")
    text = "Rollback probe รายได้ 6,501-12,500 บาท"
    digest = fingerprint(text)
    version = source["properties"]["source_id"] + "@" + digest[:16]
    graph = {"status": "EXPERIMENTAL_NOT_FOR_RETRIEVAL", "snapshot_hash": "SYNTHETIC_ROLLBACK_ONLY",
        "nodes": [source,
            {"id": "probe-version", "label": "DocumentVersion", "properties": {**state, "version_id": version,
                "content_hash": digest, "published_at": "2026-10-31", "effective_from": None,
                "document_status": "UNKNOWN", "verification_status": "UNVERIFIED"}},
            {"id": "probe-chunk", "label": "Chunk", "properties": {**state, "chunk_id": "rollback#0001", "content": text, "page": 1}},
            {"id": "probe-entity", "label": "Entity", "properties": {**state, "kind": "procedure", "name": "Rollback probe", "scope_text": "Synthetic only"}},
            {"id": "probe-fact", "label": "Fact", "properties": {**state, "kind": "fact", "predicate": "synthetic_income",
                "raw_text": text, "value_number": None, "value_text": None, "operator": "BETWEEN", "unit": "บาท",
                "scope_text": "Synthetic only", "is_approximate": False, "value_lower": 6501, "value_upper": 12500,
                "lower_inclusive": None, "upper_inclusive": None}}],
        "edges": [{"source": a, "type": relation, "target": b, "properties": props} for a, relation, b, props in [
            (source["id"], "HAS_VERSION", "probe-version", {}), ("probe-version", "HAS_CHUNK", "probe-chunk", {}),
            ("probe-entity", "MENTIONED_IN", "probe-chunk", {}), ("probe-fact", "ABOUT", "probe-entity", {}),
            ("probe-fact", "SUPPORTED_BY", "probe-chunk", {"quote": text})]]}
    probe = make_plan(graph, current["schema"])
    if probe["run_id"] == current["run_id"]:
        raise ValueError("New edition did not receive an isolated namespace")
    before = session.execute_read(other_content, probe["run_id"])
    existing = session.execute_read(read_run, probe["run_id"])
    if existing["nodes"] or existing["edges"]:
        raise ValueError("Synthetic probe namespace already exists; refusing to alter it")
    with session.begin_transaction() as tx:
        merge_run(tx, probe)
        assert_run(tx, current)
        row = tx.run("""MATCH (v:MODSAPilot {run_id:$run_id,node_id:'probe-version'}),
            (f:MODSAPilot {run_id:$run_id,node_id:'probe-fact'})
            RETURN v.published_at AS published, f.value_lower AS lower, f.value_upper AS upper,
                   properties(f)['lower_inclusive'] AS inclusive, f.retrieval_enabled AS enabled""", run_id=probe["run_id"]).single()
        if row["published"].to_native() != date(2026, 10, 31) or (row["lower"], row["upper"], row["inclusive"], row["enabled"]) != (6501, 12500, None, False):
            raise ValueError("Synthetic date/range/null/False roundtrip failed")
        tx.rollback()
    remaining = session.execute_read(read_run, probe["run_id"])
    if remaining["nodes"] or remaining["edges"] or before != session.execute_read(other_content, probe["run_id"]):
        raise ValueError("Synthetic rollback changed persistent data")
    return {"status": "PASSED_AND_ROLLED_BACK", "same_source_identity": True, "old_run_unchanged": True,
        "date_and_between_roundtrip": True, "probe_nodes_remaining": 0, "probe_edges_remaining": 0}


def write_report(plan: dict, result: dict) -> None:
    output = {"status": "LOADED_TWICE_VERIFIED_NOT_FOR_RETRIEVAL", "run_id": plan["run_id"],
        "graph_hash": plan["graph_hash"], "snapshot_hash": plan["snapshot_hash"], "schema_hash": plan["schema_hash"],
        "schema_version": plan["schema_version"], "verified_at": datetime.now(timezone.utc).isoformat(),
        "counts": {"nodes": len(plan["nodes"]), "edges": len(plan["edges"])}, **result}
    (DATA / "results/neo4j.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Phase 9 — Neo4j pilot", "", "[กลับหน้าหลัก](../README.md)", "",
        f"โหลดและตรวจชุดปัจจุบันแล้ว: {len(plan['nodes'])} nodes / {len(plan['edges'])} edges. ทุก node ยัง PENDING และปิด retrieval.", "",
        "| ตรวจอะไร | ผล |", "| --- | --- |", "| รอบแรก | ตรวจ node/edge/property sets ตรง export ทั้งชุด |",
        f"| รันซ้ำ | สร้างเพิ่ม {result['second_load']['nodes_created']} nodes / {result['second_load']['relationships_created']} edges; เนื้อหาเดิมไม่เปลี่ยน |",
        "| หลักฐาน | เก็บหลาย quote ต่อคู่ node ได้ครบ ไม่รวม evidence จนหาย |",
        "| ข้อมูลเดิมนอก run | fingerprint ของ nodes/edges/properties ก่อน–หลังตรงกัน |",
        "| รุ่นใหม่และชนิดข้อมูลจำลอง | SourceDocument ID เดิมอยู่ได้คนละ run; DATE/BETWEEN/null/False ตรวจใน DB จริงแล้ว rollback ไม่เหลือข้อมูลทดสอบ |", "",
        f"Schema `{plan['schema_version']}` · run `{plan['run_id']}`", "",
        "ขอบเขต: แยกด้วย label MODSAPilot และ run_id; ไม่มีการลบกราฟเก่า, เปิด ACTIVE, เรียก LLM หรือแก้ Chroma.",
        "ค่านโยบายที่ไม่ทราบยังไม่ทราบ; null เก็บเป็น property ที่ไม่มีค่าใน Neo4j ไม่ใช่สตริง 'null'.", "",
        "ยังไม่ทดสอบ workflow update/supersede/delete หรือ retrieval/evaluation; DATE/BETWEEN ทดสอบด้วยข้อมูลจำลองเท่านั้น ไม่ใช่วันที่หรือเกณฑ์ใหม่ของเอกสารจริง.", "",
        "## ตรวจซ้ำแบบไม่เขียนฐานข้อมูล", "", "```sh", ".venv/bin/python graph/build/load_graph.py --inspect", "```", "",
        "## ดูกราฟใน Neo4j Browser", "", "เปิด [Neo4j Browser](http://127.0.0.1:17474) แล้วใช้รหัสผ่านใน .graph-pilot.env (อย่าเผยแพร่ไฟล์นี้).", "", "```cypher",
        f"MATCH (a:MODSAPilot {{run_id:'{plan['run_id']}'}})-[r]->(b:MODSAPilot)", "RETURN a,r,b LIMIT 80;", "```", "",
        "[ผล JSON สำหรับโปรแกรม](../results/neo4j.json)", ""]
    (DATA / "review/neo4j.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--load", action="store_true")
    args = parser.parse_args()
    password = ""
    try:
        plan = prepare_import()
        if args.check:
            print(f"CHECK OK: {len(plan['nodes'])} nodes / {len(plan['edges'])} edges; no credentials, network or writes")
            return
        uri, user, password, database = connection_settings()
        from neo4j import GraphDatabase
        with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10,
                connection_acquisition_timeout=10, max_transaction_retry_time=10) as driver:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                if args.inspect:
                    existing = session.execute_read(read_run, plan["run_id"])
                    if existing["nodes"] or existing["edges"]:
                        session.execute_read(assert_run, plan)
                    outside = session.execute_read(other_content, plan["run_id"])
                    print(f"INSPECT: {len(existing['nodes'])}/{len(plan['nodes'])} nodes; {len(existing['edges'])}/{len(plan['edges'])} edges; unrelated {outside['nodes']}/{outside['edges']}; no writes")
                    return
                session.run(CONSTRAINT).consume()
                constraints = list(session.run("SHOW CONSTRAINTS YIELD type, labelsOrTypes, properties RETURN type, labelsOrTypes, properties"))
                if not any("UNIQUENESS" in row["type"] and row["labelsOrTypes"] == [LABEL] and row["properties"] == ["run_id", "node_id"] for row in constraints):
                    raise ValueError("Pilot identity uniqueness constraint is missing")
                first = session.execute_write(merge_run, plan)
                second = session.execute_write(merge_run, plan)
                if second["nodes_created"] or second["relationships_created"] or first["content_hash"] != second["content_hash"] or first["unrelated_graph"] != second["unrelated_graph"]:
                    raise ValueError("Idempotency verification failed")
                probe = version_probe(session, plan)
                result = {"first_load": first, "second_load": second, "version_probe": probe, "server": driver.get_server_info().agent}
        write_report(plan, result)
        print(f"VERIFIED: {len(plan['nodes'])} nodes / {len(plan['edges'])} edges; second load created 0/0; no retrieval activation")
    except ImportError:
        parser.exit(1, "Install graph/build/requirements.txt into .venv before live Neo4j checks\n")
    except Exception as error:
        message = str(error).replace(password, "[REDACTED]") if password else str(error)
        parser.exit(1, f"Neo4j pilot failed ({type(error).__name__}): {message[:400]}\n")


if __name__ == "__main__":
    main()
