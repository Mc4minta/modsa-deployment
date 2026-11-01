"""Build the frozen pilot manifest; no schema discovery or answer experiments."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from common import DATA, ROOT, canonical, fingerprint
from contracts import SourceNotes

OUTPUT = DATA
INPUT = OUTPUT / "inputs"


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_path: str
    title: str
    category: str
    content_hash: str
    version_id: str
    published_at: date | None = None
    effective_from: date | None = None
    document_status: Literal["UNKNOWN", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"] = "UNKNOWN"
    verification_status: Literal["PENDING", "UNVERIFIED", "VERIFIED"] = "PENDING"


class PilotChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pilot_id: str
    chunk_id: str
    source_id: str
    version_id: str
    source_index: int = Field(ge=0)
    category: str
    page: int | None = Field(default=None, ge=1)
    content: str = Field(min_length=1)
    role: Literal["primary", "context", "vector_only"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pilot_id: str
    quote: str = Field(min_length=1)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    question: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    claims: list[Claim]
    evidence_sets: list[list[str]]
    review_status: Literal["DRAFT", "NEEDS_REVIEW", "APPROVED"] = "DRAFT"
    notes: list[str] = Field(default_factory=list)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def check_aliases(aliases: dict, chunks: dict[str, PilotChunk]) -> None:
    keys = set()
    for entry in aliases["entries"]:
        quotes = [e["quote"] for e in entry["evidence"]]
        if not quotes or any(e["pilot_id"] not in chunks or e["quote"] not in chunks[e["pilot_id"]].content for e in entry["evidence"]):
            raise ValueError("Alias evidence not in source")
        for name in [entry["canonical_name"], *entry["aliases"]]:
            key = (entry["kind"], entry["scope"], name)
            if not name or not any(name in quote for quote in quotes):
                raise ValueError("Every alias name requires its own source evidence")
            if key in keys:
                raise ValueError("Ambiguous alias mapping")
            keys.add(key)
    check_frozen(aliases)


def check_schema_upgrade(previous: dict, current: dict) -> dict:
    """Allow explicit legacy replay only for unchanged data and additive schema."""
    for bundle in (previous, current):
        if bundle.get("snapshot_hash") != fingerprint({k: v for k, v in bundle.items() if k != "snapshot_hash"}):
            raise ValueError("Invalid preparation snapshot fingerprint")
    data = lambda b: {k: v for k, v in b.items() if k not in {"schema", "aliases", "snapshot_hash", "status", "purpose"}}
    if data(previous) != data(current):
        raise ValueError("Schema replay cannot adopt changed source, pilot or question data")
    old, new = previous["schema"], current["schema"]
    check_schema(new)
    excluded = {"node_types", "relationship_types", "schema_version", "status", "fingerprint"}
    if {k: v for k, v in old.items() if k not in excluded} != {k: v for k, v in new.items() if k not in excluded}:
        raise ValueError("Schema replay requires unchanged graph patterns")
    for collection in ("node_types", "relationship_types"):
        before, after = ({r["label"]: r for r in s[collection]} for s in (old, new))
        if before.keys() != after.keys():
            raise ValueError("Schema replay cannot change graph labels")
        for label, record in before.items():
            if {k: v for k, v in record.items() if k != "properties"} != {k: v for k, v in after[label].items() if k != "properties"}:
                raise ValueError("Schema replay cannot change label semantics")
            properties = {p["name"]: p for p in after[label].get("properties", [])}
            if any(properties.get(p["name"]) != p for p in record.get("properties", [])):
                raise ValueError("Schema replay cannot remove or retype properties")
    old_aliases = {(e["kind"], e["scope"], e["canonical_name"]): e for e in previous["aliases"]["entries"]}
    for entry in current["aliases"]["entries"]:
        before = old_aliases.get((entry["kind"], entry["scope"], entry["canonical_name"]))
        if not before or not set(entry["aliases"]) <= set(before["aliases"]) or entry["evidence"] != before["evidence"]:
            raise ValueError("Schema replay may only narrow existing source-backed aliases")
    check_aliases(current["aliases"], {c["pilot_id"]: PilotChunk.model_validate(c) for c in current["pilot"]})
    return {"kind": "EXPLICIT_ADDITIVE_SCHEMA_REVALIDATION_NOT_NEW_LLM_RUN",
        "from_snapshot_hash": previous["snapshot_hash"], "to_snapshot_hash": current["snapshot_hash"],
        "source_input_hash": fingerprint(data(current)), "previous_schema": old,
        "target_schema_hash": fingerprint(new), "schema_version": new.get("schema_version")}


def check_questions(questions: list[Question], chunks: dict[str, PilotChunk]) -> None:
    expected = {f"p{i:02d}" for i in range(1, 26)} | {f"m{i:02d}" for i in range(1, 16)} | {f"n{i:02d}" for i in range(1, 11)}
    if len(questions) != 50 or {q.id for q in questions} != expected:
        raise ValueError("Expected 50 unique development question IDs")
    for question in questions:
        evidence_ids = set()
        for claim in question.claims:
            for evidence in claim.evidence:
                if evidence.pilot_id not in chunks or evidence.quote not in chunks[evidence.pilot_id].content:
                    raise ValueError(f"{question.id}: quote not found in {evidence.pilot_id}")
                evidence_ids.add(evidence.pilot_id)
        for alternative in question.evidence_sets:
            if not alternative or len(set(alternative)) != len(alternative) or not set(alternative) <= chunks.keys():
                raise ValueError(f"{question.id}: invalid evidence set")
            if question.claims and any(not any(e.pilot_id in alternative for e in c.evidence) for c in question.claims):
                raise ValueError(f"{question.id}: evidence set misses an answer claim")
        covered = {p for alternative in question.evidence_sets for p in alternative}
        if not evidence_ids <= covered:
            raise ValueError(f"{question.id}: cited evidence absent from evidence sets")
        if question.kind == "not_in_snapshot":
            if question.claims or question.evidence_sets:
                raise ValueError(f"{question.id}: absent answer must not have positive gold evidence")
        elif not question.claims or not question.evidence_sets:
            raise ValueError(f"{question.id}: expected answer requires supporting claims/evidence")


def build() -> dict:
    documents, all_ids, chunk_ids = {}, set(), set()
    inventory = Counter()
    for path in sorted((ROOT / "data/chunks").rglob("*.json")):
        document = read(path)
        doc_id = document["doc_id"]
        if doc_id in all_ids:
            raise ValueError(f"Duplicate doc_id: {doc_id}")
        all_ids.add(doc_id)
        category = path.parent.name
        inventory[category] += len(document["chunks"])
        for chunk in document["chunks"]:
            if chunk["chunk_id"] in chunk_ids:
                raise ValueError(f"Duplicate chunk_id: {chunk['chunk_id']}")
            chunk_ids.add(chunk["chunk_id"])
        documents[str(path.relative_to(ROOT / "data/chunks"))] = document
    notes_path = INPUT / "source_notes.json"
    notes = read(notes_path) if notes_path.exists() else {}
    if not isinstance(notes, dict) or not notes.keys() <= all_ids:
        raise ValueError("source_notes.json must map existing source IDs to reviewed metadata")
    allowed_notes = set(SourceNotes.model_fields)
    for source_id, reviewed in notes.items():
        if not isinstance(reviewed, dict) or not reviewed.keys() <= allowed_notes:
            raise ValueError(f"{source_id}: source notes may only set dates/statuses, not IDs or hashes")
        notes[source_id] = SourceNotes.model_validate(reviewed).model_dump(mode="json", exclude_unset=True)
    selected = read(INPUT / "pilot.json")["chunks"]
    sources, chunks = {}, []
    for entry in selected:
        pilot_id, file, role = entry["pilot_id"], entry["source_path"], entry["role"]
        document = documents[file]
        matches = [(i, c) for i, c in enumerate(document["chunks"]) if c["chunk_id"] == entry["chunk_id"]]
        if len(matches) != 1:
            raise ValueError(f"{pilot_id}: selected source chunk missing or ambiguous")
        index, raw = matches[0]
        meta = document.get("metadata", {})
        source_id = document["doc_id"]
        content_hash = fingerprint([{k: c.get(k) for k in ("content", "page", "section")} for c in document["chunks"]])
        if source_id not in sources:
            view = {**meta, **notes.get(source_id, {})}
            reviewed = {"verification_status": view.get("verification_status") or ("VERIFIED" if view.get("verified") is True else "UNVERIFIED" if view.get("verified") is False else "PENDING"),
                "published_at": view.get("published_at") or None, "effective_from": view.get("effective_from") or None,
                "document_status": view.get("document_status") or "UNKNOWN"}
            sources[source_id] = SourceRecord(source_id=source_id, source_path=file, title=view.get("title") or source_id,
                category=file.split("/")[0], content_hash=content_hash, version_id=f"{source_id}@{content_hash[:16]}",
                **reviewed)
        source = sources[source_id]
        chunks.append(PilotChunk(pilot_id=pilot_id, chunk_id=raw["chunk_id"], source_id=source_id,
            version_id=source.version_id, source_index=index, category=source.category,
            page=raw.get("page"), content=raw["content"], role=role))
    if len(chunks) != 27 or len({c.chunk_id for c in chunks}) != 27 or len({c.pilot_id for c in chunks}) != 27:
        raise ValueError("Expected 27 unique pilot chunks")
    qa_input = read(INPUT / "questions.json")
    questions = [Question.model_validate(q) for q in qa_input["questions"]]
    check_questions(questions, {c.pilot_id: c for c in chunks})
    schema, aliases = read(INPUT / "schema.json"), read(INPUT / "aliases.json")
    check_schema(schema)
    check_aliases(aliases, {c.pilot_id: c for c in chunks})
    bundle = {"status": "DEVELOPMENT_DRAFT_WITH_FROZEN_SCHEMA", "purpose": "GraphRAG pilot development; not production knowledge or a held-out benchmark",
        "inventory": {"documents": len(documents), "chunks": len(chunk_ids), "categories": dict(inventory)},
        "sources": [s.model_dump(mode="json") for s in sources.values()],
        "pilot": [c.model_dump() for c in chunks], "questions": [q.model_dump() for q in questions],
        "schema": schema, "aliases": aliases}
    # Preserve the historical inventory of an unchanged frozen pilot. Live corpus
    # counts belong in contracts.json, not in the identity of unrelated pilot jobs.
    previous_path = OUTPUT / "results/bundle.json"
    if previous_path.exists():
        previous = read(previous_path)
        identity = lambda b: {k: v for k, v in b.items() if k not in {"inventory", "snapshot_hash"}}
        valid = previous.get("snapshot_hash") == fingerprint({k: v for k, v in previous.items() if k != "snapshot_hash"})
        if valid and identity(previous) == identity(bundle):
            bundle["inventory"] = previous["inventory"]
    bundle["snapshot_hash"] = fingerprint(bundle)
    return bundle


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def extraction_status(bundle: dict, extraction: dict | None, graph: dict | None) -> dict:
    current = bool(extraction and graph and extraction.get("snapshot_hash") == bundle["snapshot_hash"] == graph.get("snapshot_hash"))
    records = extraction.get("records", {}) if current else {}
    staged = extraction.get("staged", {}) if current else {}
    primary = {c["pilot_id"] for c in bundle["pilot"] if c["role"] == "primary"}
    checked = set(extraction.get("source_checked_ids", [])) & records.keys() if current else set()
    rejected = sum(len(s.get("rejected", [])) for s in staged.values())
    with_facts = {pid for pid, s in staged.items() if s.get("facts")}
    previous_schema = extraction.get("schema_revalidation", {}).get("previous_schema") if current else None
    baseline = sum(r.get("schema_hash") == fingerprint(previous_schema) for r in records.values()) if previous_schema else 0
    return {"current": current, "records": len(records), "primary": len(primary), "checked": len(checked),
        "rejected": rejected, "unresolved": sum(len(s.get("unresolved", [])) for s in staged.values()),
        "baseline": baseline, "additional": len(records) - baseline,
        "ready": records.keys() == primary and primary <= with_facts and primary <= checked and rejected == 0}


def neo4j_status(bundle: dict, graph: dict | None, result: dict | None) -> bool:
    """Match saved verification to exact export/configuration, not live DB health."""
    if not isinstance(graph, dict) or not isinstance(result, dict) or graph.get("snapshot_hash") != bundle["snapshot_hash"]:
        return False
    first, second = result.get("first_load", {}), result.get("second_load", {})
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    return (result.get("status") == "LOADED_TWICE_VERIFIED_NOT_FOR_RETRIEVAL"
        and result.get("graph_hash") == fingerprint(graph)
        and result.get("snapshot_hash") == bundle["snapshot_hash"]
        and result.get("schema_hash") == fingerprint(bundle["schema"])
        and result.get("run_id") == bundle["schema"]["schema_version"] + ":" + fingerprint({"graph_hash": fingerprint(graph), "schema_hash": fingerprint(bundle["schema"])})
        and result.get("counts") == {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
        and type(second.get("nodes_created")) is int and second["nodes_created"] == 0
        and type(second.get("relationships_created")) is int and second["relationships_created"] == 0
        and isinstance(first.get("content_hash"), str) and bool(first["content_hash"]) and first["content_hash"] == second.get("content_hash")
        and bool(first.get("unrelated_graph")) and first.get("unrelated_graph") == second.get("unrelated_graph"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without API, DB or file writes")
    args = parser.parse_args()
    bundle = build()
    path = OUTPUT / "results/bundle.json"
    if args.check:
        if not path.exists() or read(path) != bundle:
            parser.error("Bundle differs; inspect inputs then regenerate with prepare.py")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'CHECK OK' if args.check else 'PREPARED'}: {len(bundle['pilot'])} pilot chunks; frozen schema; no API/DB/source writes")


if __name__ == "__main__":
    main()
