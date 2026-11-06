"""Validated, content-addressed Neo4j import/readback primitives; no CLI side effects."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import json
import math
import hashlib
import os
import re
from urllib.parse import urlsplit

from common import DATA, ROOT, fingerprint
from contracts import NumericRange
from prepare import check_schema

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


def batch_verification(path, content_hashes: dict) -> dict:
    """Describe verified readback, independently of extraction caches or API calls."""
    output = read(path)
    run_ids = [document["run_id"] for document in output["documents"]]
    if len(run_ids) != len(set(run_ids)) or set(run_ids) != set(content_hashes):
        raise ValueError("Readback run set differs from the batch")
    return {"status":"READBACK_VERIFIED_PENDING_NOT_FOR_RETRIEVAL", "batch_id":output["batch_id"],
        "verified_at_utc":datetime.now(timezone.utc).isoformat(),
        "graph_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "documents":len(run_ids), "target_run_ids":run_ids, "target_content_hashes":content_hashes,
        "nodes":sum(len(d["graph"]["nodes"]) for d in output["documents"]),
        "edges":sum(len(d["graph"]["edges"]) for d in output["documents"]),
        "all_nodes_pending_retrieval_disabled":all(n["properties"].get("review_status")=="PENDING"
            and n["properties"].get("retrieval_enabled") is False for d in output["documents"] for n in d["graph"]["nodes"]),
        "new_llm_api_calls":0, "semantic_accuracy_approved":False}


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
