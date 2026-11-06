"""Validate the graph schema; no pilot files, source reads or side effects."""
from common import fingerprint


def check_schema(schema: dict) -> None:
    labels = [n["label"] for n in schema["node_types"]]
    relations = [r["label"] for r in schema["relationship_types"]]
    if len(labels) != len(set(labels)) or len(relations) != len(set(relations)):
        raise ValueError("Duplicate schema label")
    if set(labels) != {"SourceDocument", "DocumentVersion", "Chunk", "Entity", "Offering", "Fact"}:
        raise ValueError("Unexpected schema labels; review the preparation contract")
    patterns = schema["patterns"]
    if len({tuple(p) for p in patterns}) != len(patterns):
        raise ValueError("Duplicate schema pattern")
    for source, relation, target in patterns:
        if source not in labels or target not in labels or relation not in relations:
            raise ValueError(f"Unknown endpoint/type: {source} {relation} {target}")
    for record in [*schema["node_types"], *schema["relationship_types"]]:
        properties = record.get("properties", [])
        if len({p["name"] for p in properties}) != len(properties):
            raise ValueError(f"Duplicate property in {record['label']}")
        if any(p["type"] not in {"STRING", "STRING_LIST", "FLOAT", "INTEGER", "BOOLEAN", "DATE"} for p in properties):
            raise ValueError(f"Unsupported property type in {record['label']}")
    if ["Fact", "SUPPORTED_BY", "Chunk"] not in patterns:
        raise ValueError("Missing evidence path")
    required = {
        ("SourceDocument", "HAS_VERSION", "DocumentVersion"), ("DocumentVersion", "HAS_CHUNK", "Chunk"),
        ("Chunk", "NEXT_CHUNK", "Chunk"), ("Entity", "MENTIONED_IN", "Chunk"),
        ("Offering", "MENTIONED_IN", "Chunk"), ("Fact", "ABOUT", "Entity"),
        ("Fact", "ABOUT", "Offering"), ("Entity", "HAS_OFFERING", "Offering"),
        ("Offering", "HAS_TRACK", "Entity"),
    }
    if not required <= {tuple(p) for p in patterns}:
        raise ValueError("Missing source, subject or scope paths required by the preparation contract")
    check_frozen(schema)


def check_frozen(value: dict) -> None:
    if value.get("status") == "FROZEN_FOR_PILOT_NOT_POLICY_APPROVAL":
        if value.get("fingerprint") != fingerprint({k: v for k, v in value.items() if k != "fingerprint"}):
            raise ValueError("Frozen configuration changed; review and version it before use")
