"""Read-only structural diagnosis of a pinned dev retrieval replay, not a retriever."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time

import retrieve


def subject_index(graph):
    mentions, evidence = defaultdict(set), defaultdict(set)
    for edge in graph.edges.values():
        if edge["type"] == "MENTIONED_IN":
            mentions[edge["source"]].add(edge["target"])
        elif edge["type"] == "ABOUT":
            for _, support in graph.outgoing[edge["source"]]:
                if support["type"] == "SUPPORTED_BY":
                    evidence[edge["target"]].add(support["target"])
    return mentions, evidence


def candidates(graph, seeds):
    """Exact existing walker paths/order without its result cap; no new edge types."""
    seed_nodes = [graph.anchor(doc) for doc in seeds]
    if any(node is None for node in seed_nodes):
        raise ValueError("Stale seed in pinned replay")
    result = {}

    def offer(seed, target, kind, edge_ids):
        if (target in graph.chunks and target not in seed_nodes
                and graph.versions[target] == graph.versions[seed]):
            result.setdefault(target, []).append({"seed_chunk_id": graph.chunks[seed].metadata["chunk_id"],
                                                 "kind": kind, "edge_ids": edge_ids})

    for seed in seed_nodes:
        for edge_id, edge in graph.outgoing[seed] + graph.incoming[seed]:
            if edge["type"] == "NEXT_CHUNK":
                offer(seed, edge["target"] if edge["source"] == seed else edge["source"], "adjacent", [edge_id])
        for mention_id, mention in graph.incoming[seed]:
            subject = mention["source"]
            if mention["type"] != "MENTIONED_IN" or graph.nodes[subject]["label"] not in {"Entity", "Offering"}:
                continue
            for about_id, about in graph.incoming[subject]:
                if about["type"] != "ABOUT" or graph.nodes[about["source"]]["label"] != "Fact":
                    continue
                for support_id, support in graph.outgoing[about["source"]]:
                    if support["type"] == "SUPPORTED_BY":
                        offer(seed, support["target"], "fact_evidence", [mention_id, about_id, support_id])
    return result


def identity_groups(graph):
    groups = defaultdict(list)
    for key, node in graph.nodes.items():
        if node["label"] == "Entity":
            props = node["properties"]
            groups[(key.rsplit("/", 1)[0], props["kind"], props["name"])].append(key)
    return {key: value for key, value in groups.items() if len(value) > 1}


def semantic_components(chunk_nodes, mentions, evidence):
    # Structural diagnostic only: ignore direction, adjacency and document-parent hubs.
    links = defaultdict(set)
    for subject in mentions.keys() | evidence.keys():
        chunks = mentions[subject] | evidence[subject]
        if chunks:
            first = min(chunks)
            for chunk in chunks - {first}:
                links[first].add(chunk)
                links[chunk].add(first)
    remaining, components, sizes = set(chunk_nodes), {}, []
    while remaining:
        todo, size = [remaining.pop()], 0
        while todo:
            current = todo.pop()
            components[current] = len(sizes)
            size += 1
            for neighbor in links[current] & remaining:
                remaining.remove(neighbor)
                todo.append(neighbor)
        sizes.append(size)
    return components, sizes


def diagnose(graph, replay):
    mentions, evidence = subject_index(graph)
    subjects = [key for key, node in graph.nodes.items() if node["label"] in {"Entity", "Offering"}]
    groups = identity_groups(graph)
    components, component_sizes = semantic_components(graph.chunks, mentions, evidence)
    subject_group = {subject: members for members in groups.values() for subject in members}
    supporting_facts = defaultdict(set)
    for key, edge in graph.edges.items():
        if edge["type"] == "SUPPORTED_BY":
            supporting_facts[edge["target"]].add(edge["source"])
    rows, reasons = [], Counter()
    for row in replay["rows"]:
        seeds = [graph.documents[next(key for key in graph.documents if key[1] == chunk)]
                 for chunk in row["variants"]["vector4"]["chunk_ids"]]
        reachable = candidates(graph, seeds)
        for cap in (4, 20):
            actual, _ = graph.expand(seeds, limit=cap)
            expected = [graph.chunks[key] for key in list(reachable)[:cap]]
            if actual != expected:
                raise ValueError("Audit traversal differs from runtime")
        selected, _ = graph.expand(seeds, limit=4)
        ids = [doc.metadata["chunk_id"] for doc in seeds + selected]
        if ids != row["variants"]["graph4_plus4"]["chunk_ids"]:
            raise ValueError("Replay output drift")
        if not row["answerable"] or not row["gold_chunk_ids"]:
            continue
        seed_nodes = {graph.anchor(doc) for doc in seeds}
        seed_versions = {graph.versions[key] for key in seed_nodes}
        seed_subjects = {subject for subject in subjects if mentions[subject] & seed_nodes}
        reachable_ids = {graph.chunks[key].metadata["chunk_id"] for key in reachable}
        missing = []
        for gold in row["gold_chunk_ids"]:
            if gold in ids:
                continue
            matches = [key for key in graph.chunks if graph.chunks[key].metadata["chunk_id"] == gold]
            if len(matches) != 1:
                raise ValueError("Gold chunk absent or ambiguous")
            target = matches[0]
            if target in reachable:
                reason = "reachable_but_cut_by_limit"
            elif graph.versions[target] not in seed_versions:
                reason = "outside_seed_document_versions"
            else:
                reason = "same_version_but_no_current_path"
            split_hints = []
            for subject in subjects:
                if target not in evidence[subject]:
                    continue
                for other in set(subject_group.get(subject, [])) & seed_subjects:
                    if other != subject:
                        split_hints.append({"seed_subject": other, "gold_subject": subject,
                            "name": graph.nodes[subject]["properties"]["name"],
                            "seed_scope": graph.nodes[other]["properties"]["scope_text"],
                            "gold_scope": graph.nodes[subject]["properties"]["scope_text"]})
            missing.append({"chunk_id": gold, "reason": reason, "supported_fact_count": len(supporting_facts[target]),
                            "same_undirected_semantic_component_as_seed": any(components[target] == components[s] for s in seed_nodes),
                            "current_paths": reachable.get(target, []), "exact_name_split_hints_not_merge_approval": split_hints})
            reasons[reason] += 1
        gold_set = set(row["gold_chunk_ids"])
        seed_ids = {doc.metadata["chunk_id"] for doc in seeds}
        extra_gold = (reachable_ids & gold_set) - seed_ids
        rows.append({"question_id": row["question_id"], "question": row["question"], "missing": missing,
            "all_current_candidate_count": len(reachable),
            "oracle_recall_with_same_4_addition_budget": (len(seed_ids & gold_set) + min(4, len(extra_gold))) / len(gold_set),
            "unlimited_current_path_recall": len((seed_ids | reachable_ids) & gold_set) / len(gold_set)})

    split_details = [{"run_id": key[0], "kind": key[1], "name": key[2], "nodes": [
        {"node_id": subject, "scope_text": graph.nodes[subject]["properties"]["scope_text"],
         "mentioned_chunks": sorted(graph.chunks[c].metadata["chunk_id"] for c in mentions[subject]),
         "fact_evidence_chunks": sorted(graph.chunks[c].metadata["chunk_id"] for c in evidence[subject])}
        for subject in members]} for key, members in sorted(groups.items())]
    summary = {"entity_nodes": sum(n["label"] == "Entity" for n in graph.nodes.values()),
        "offering_nodes": sum(n["label"] == "Offering" for n in graph.nodes.values()),
        "subjects_mentioned_in_multiple_chunks": sum(len(mentions[s]) > 1 for s in subjects),
        "subjects_with_actual_cross_chunk_fact_path": sum(any(a != b for a in mentions[s] for b in evidence[s]) for s in subjects),
        "chunks_with_supported_facts": len(supporting_facts), "chunk_count": len(graph.chunks),
        "semantic_component_count": len(component_sizes), "isolated_chunks_without_semantic_bridge": component_sizes.count(1),
        "largest_semantic_component_chunks": max(component_sizes, default=0),
        "same_version_exact_kind_name_split_groups": len(groups), "nodes_in_split_groups": sum(map(len, groups.values())),
        "dev_answerable_questions": len(rows), "questions_missing_gold": sum(bool(r["missing"]) for r in rows),
        "missing_gold_occurrences": sum(reasons.values()), "missing_reason_counts": dict(reasons),
        "missing_occurrences_with_exact_name_split_hint": sum(bool(m["exact_name_split_hints_not_merge_approval"]) for r in rows for m in r["missing"]),
        "missing_occurrences_without_supported_facts": sum(not m["supported_fact_count"] for r in rows for m in r["missing"]),
        "missing_no_current_path_but_same_undirected_semantic_component": sum(
            m["reason"] == "same_version_but_no_current_path" and m["same_undirected_semantic_component_as_seed"]
            for r in rows for m in r["missing"]),
        "oracle_mean_recall_same_4_addition_budget": statistics.mean(r["oracle_recall_with_same_4_addition_budget"] for r in rows),
        "unlimited_current_path_mean_recall": statistics.mean(r["unlimited_current_path_recall"] for r in rows)}
    return {"summary": summary, "questions": rows, "split_identity_candidates_not_approved": split_details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve prior audit; choose new output directory")
    start = time.perf_counter()
    saved = retrieve.read(args.replay)
    dataset = retrieve.ROOT / "data/evaluation/eval_311026.json"
    if (saved["split"] != "dev" or saved["pins"]["export_sha256"] != retrieve.file_hash(args.export)
            or saved["pins"]["dataset_sha256"] != retrieve.file_hash(dataset)
            or saved["pins"]["walker_sha256"] != retrieve.file_hash(retrieve.ROOT / "backend/services/graph_service.py")):
        raise ValueError("Pinned graph/dataset/walker drift")
    dev = {q["question_id"]: q for q in retrieve.read(dataset) if q["split"] == "dev"}
    if len(saved["rows"]) != len(dev) or {r["question_id"] for r in saved["rows"]} != set(dev):
        raise ValueError("Audit must use the complete dev split only")
    for row in saved["rows"]:
        if any(row[k] != dev[row["question_id"]][k] for k in ("question", "answerable", "gold_chunk_ids")):
            raise ValueError("Pinned dev row drift")
    graph, _, _ = retrieve.snapshot_graph(retrieve.read(args.export), retrieve.read(args.export.with_name("load_verification.json")))
    result = diagnose(graph, saved)
    result.update(status="OFFLINE_CONNECTIVITY_DIAGNOSIS_NOT_RETRIEVAL_SCORE_OR_MERGE_APPROVAL",
        created_at=datetime.now(timezone.utc).isoformat(), pins={"export_sha256": retrieve.file_hash(args.export),
            "replay_sha256": retrieve.file_hash(args.replay), "script_sha256": retrieve.file_hash(Path(__file__)),
            "walker_sha256": saved["pins"]["walker_sha256"]}, new_api_calls=0, new_tokens=0, database_writes=False,
        wall_seconds=time.perf_counter() - start)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
