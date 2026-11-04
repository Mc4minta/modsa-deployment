"""Offline dev replay: frozen Vector results -> existing bounded graph expansion.

No model, embeddings, database connection, policy activation or reranking.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "graph/build"))

from common import fingerprint
from langchain_core.documents import Document
from services.graph_service import PilotGraph

VARIANTS = ("vector4", "vector8", "adjacent4_plus4", "graph4_plus4")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def snapshot_graph(export: dict, verified: dict) -> tuple[PilotGraph, PilotGraph, dict]:
    if (verified["batch_id"] != export["batch_id"]
            or not verified["all_nodes_pending_retrieval_disabled"]
            or set(verified["target_run_ids"]) != {d["run_id"] for d in export["documents"]}):
        raise ValueError("Export is not the verified staging batch")
    nodes, edges, documents = {}, {}, []
    for item in export["documents"]:
        source, graph, run_id = item["source"], item["graph"], item["run_id"]
        raw_nodes = {n["id"]: {"label": n["label"], "properties": {
            k: v for k, v in n["properties"].items() if v is not None}} for n in graph["nodes"]}
        raw_edges = {fingerprint(e): {**e, "properties": {
            k: v for k, v in e["properties"].items() if v is not None}} for e in graph["edges"]}
        if fingerprint({"nodes": raw_nodes, "edges": raw_edges}) != verified["target_content_hashes"][run_id]:
            raise ValueError("Export content differs from Neo4j readback")
        path = (ROOT / source["source_path"]).resolve()
        if not path.is_relative_to((ROOT / "data/chunks").resolve()):
            raise ValueError("Source path outside data/chunks")
        raw = read(path)
        digest = fingerprint([{k: c.get(k) for k in ("content", "page", "section")} for c in raw["chunks"]])
        if digest != source["content_hash"] or raw["doc_id"] != source["source_id"]:
            raise ValueError("Source version drift")
        chunk_nodes = {n["properties"]["chunk_id"]: n["properties"]
                       for n in graph["nodes"] if n["label"] == "Chunk"}
        if set(chunk_nodes) != {c["chunk_id"] for c in raw["chunks"]}:
            raise ValueError("Graph/source chunk coverage differs")
        for index, chunk in enumerate(raw["chunks"]):
            props = chunk_nodes[chunk["chunk_id"]]
            if props["content"] != chunk["content"] or props.get("page") != chunk.get("page"):
                raise ValueError("Graph/source content or page differs")
            metadata = {k: source[k] for k in ("source_id", "version_id", "content_hash", "title",
                                               "document_status", "verification_status")}
            metadata.update(source=source["source_path"], chunk_id=chunk["chunk_id"], source_index=index,
                            category=source["topic_tags"][0], retrieval_enabled=False)
            if chunk.get("page") is not None:
                metadata["page"] = chunk["page"] - 1
            documents.append(Document(page_content=chunk["content"], metadata=metadata))
        # Neo4j identities are (run_id, node_id); keep that isolation in memory too.
        nodes.update({run_id + "/" + key: node for key, node in raw_nodes.items()})
        edges.update({run_id + "/" + key: {**edge, "source": run_id + "/" + edge["source"],
                                           "target": run_id + "/" + edge["target"]}
                      for key, edge in raw_edges.items()})
    by_chunk = {d.metadata["chunk_id"]: d for d in documents}
    if len(by_chunk) != len(documents):
        raise ValueError("Ambiguous chunk IDs across versions")
    graph = PilotGraph(nodes, edges, documents, allow_pending=True)
    adjacent = PilotGraph(nodes, {k: e for k, e in edges.items()
                                 if e["type"] in {"HAS_VERSION", "HAS_CHUNK", "NEXT_CHUNK"}},
                          documents, allow_pending=True)
    return graph, adjacent, by_chunk


def replay_seeds(question: dict, saved: dict, by_chunk: dict) -> list[Document]:
    if saved["question"] != question["question"] or saved["k_used"] != 4:
        raise ValueError("Baseline question or production k changed")
    retrieved = saved["retrieved"]
    if len(retrieved) < 8 or [r["rank"] for r in retrieved] != list(range(1, len(retrieved) + 1)):
        raise ValueError("Baseline must contain ordered top-8 or more")
    result = []
    for row in retrieved:
        doc = by_chunk.get(row["chunk_id"])
        if (doc is None or doc.page_content != row["content"]
                or doc.metadata["source_id"] != row["doc_id"]):
            raise ValueError("Cached retrieval is stale or cannot bridge exactly to graph")
        result.append(doc)
    if len({d.metadata["chunk_id"] for d in result}) != len(result):
        raise ValueError("Duplicate cached retrieval IDs")
    return result


def metrics(ids: list[str], gold_ids: list[str], budget: int) -> dict:
    gold, hits = set(gold_ids), set(ids) & set(gold_ids)
    return {"recall": len(hits) / len(gold) if gold else None,
            "precision_at_budget": len(hits) / budget if gold else None,
            "complete": gold <= set(ids) if gold else None,
            "reciprocal_rank": next((1 / i for i, key in enumerate(ids, 1) if key in gold), 0.0) if gold else None,
            "context_chunks": len(ids), "gold_hits": sorted(hits)}


def summarize(rows: list[dict]) -> dict:
    eligible = [r for r in rows if r["answerable"] and r["gold_chunk_ids"]]
    summary = {"questions": len(rows), "answerable_with_gold": len(eligible), "variants": {}}
    for variant in VARIANTS:
        values = [r["variants"][variant]["metrics"] for r in eligible]
        summary["variants"][variant] = {
            "mean_recall": statistics.mean(v["recall"] for v in values) if values else None,
            "mean_precision_at_budget": statistics.mean(v["precision_at_budget"] for v in values) if values else None,
            "complete": sum(v["complete"] for v in values),
            "mrr": statistics.mean(v["reciprocal_rank"] for v in values) if values else None,
            "mean_context_chunks": statistics.mean(r["variants"][variant]["metrics"]["context_chunks"] for r in rows)}
    for baseline in ("vector4", "vector8", "adjacent4_plus4"):
        for comparison, sign in (("improved", 1), ("regressed", -1)):
            summary[f"graph_vs_{baseline}_{comparison}"] = [r["question_id"] for r in eligible
                if sign * (r["variants"]["graph4_plus4"]["metrics"]["recall"]
                           - r["variants"][baseline]["metrics"]["recall"]) > 0]
    return summary


def evaluate(export_path: Path, baseline_path: Path, dataset_path: Path) -> dict:
    started = time.perf_counter()
    export, verified = read(export_path), read(export_path.with_name("load_verification.json"))
    if file_hash(export_path) != verified["graph_sha256"]:
        raise ValueError("Export SHA differs from staging verification")
    graph, adjacent, by_chunk = snapshot_graph(export, verified)
    questions = [q for q in read(dataset_path) if q["split"] == "dev"]
    saved_rows = [json.loads(line) for line in baseline_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    baseline = {r["question_id"]: r for r in saved_rows}
    if len(baseline) != len(saved_rows) or len({q["question_id"] for q in questions}) != len(questions):
        raise ValueError("Duplicate question IDs")
    rows = []
    for question in questions:
        # Gold is used only below for scoring, never to select seeds or walk edges.
        seeds = replay_seeds(question, baseline[question["question_id"]], by_chunk)
        contexts, paths, timings = {"vector4": seeds[:4], "vector8": seeds[:8]}, {}, {}
        for variant, walker in (("adjacent4_plus4", adjacent), ("graph4_plus4", graph)):
            t0 = time.perf_counter()
            additions, trace = walker.expand(seeds[:4], limit=4)
            timings[variant] = time.perf_counter() - t0
            contexts[variant], paths[variant] = seeds[:4] + additions, trace
            if any(p["kind"] == "bridge_rejected" for p in trace):
                raise ValueError("Exact cached seed rejected by graph")
        variants = {}
        for variant, documents in contexts.items():
            ids = [d.metadata["chunk_id"] for d in documents]
            if len(ids) != len(set(ids)) or ids[:4] != [d.metadata["chunk_id"] for d in seeds[:4]]:
                raise ValueError("Expansion duplicated or reordered vector seeds")
            variants[variant] = {"chunk_ids": ids, "metrics": metrics(ids, question["gold_chunk_ids"],
                                                                       4 if variant == "vector4" else 8)}
        rows.append({k: question[k] for k in ("question_id", "question", "category", "answerable", "gold_chunk_ids")}
                    | {"variants": variants, "paths": paths, "local_expansion_seconds": timings})
    return {"status": "OFFLINE_DEV_REPLAY_NOT_CPE_OR_ANSWER_EVAL", "created_at": datetime.now(timezone.utc).isoformat(),
            "batch_id": export["batch_id"], "pins": {"export_sha256": file_hash(export_path),
                "dataset_sha256": file_hash(dataset_path), "baseline_sha256": file_hash(baseline_path),
                "baseline_path": str(baseline_path.resolve()), "script_sha256": file_hash(Path(__file__)),
                "walker_sha256": file_hash(ROOT / "backend/services/graph_service.py")},
            "split": "dev", "seed_method": "cached_friend_bge-m3:latest_top4_exact_content_bridge",
            "scoring": "exact gold chunk IDs; macro recall; fixed-budget precision; complete = all listed gold IDs",
            "summary": summarize(rows), "by_category": {category: summarize([r for r in rows if r["category"] == category])
                for category in sorted({r["category"] for r in rows})},
            "path_kinds": dict(Counter(p["kind"] for r in rows for p in r["paths"]["graph4_plus4"])),
            "new_api_calls": 0, "new_tokens": 0, "database_writes": False, "hybrid_enabled": False,
            "wall_seconds": time.perf_counter() - started, "rows": rows}


def report(result: dict) -> str:
    summary = result["summary"]
    lines = ["# Offline Graph retrieval — dev replay", "",
        "ใช้กราฟ export ที่ SHA/content hashes ตรงกับผลอ่านกลับ Neo4j staging; ไม่เชื่อมฐานในรอบนี้.",
        "ใช้ Vector ranking ที่เพื่อนบันทึกไว้ (bge-m3:latest) และตรวจ content/source/version ตรงกันก่อนเดินกราฟเดิม.",
        "ไม่เรียก LLM/embedding API, ไม่ rerank/filter, ไม่แก้ฐาน และไม่เปิด Hybrid ใน API.", "",
        f"ชุด dev {summary['questions']} ข้อ; มี gold สำหรับวัด retrieval {summary['answerable_with_gold']} ข้อ. ไม่รันชุด test.", "",
        "| วิธี | Mean recall | หลักฐานครบ | Precision ตามงบ | Context เฉลี่ย |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for variant, m in summary["variants"].items():
        lines.append(f"| {variant} | {m['mean_recall']:.2%} | {m['complete']}/{summary['answerable_with_gold']} | {m['mean_precision_at_budget']:.2%} | {m['mean_context_chunks']:.2f} |")
    lines.extend(["", "vector8 เป็นตัวเทียบงบบริบทสูงสุด 8 chunks เท่ากราฟ; adjacent4_plus4 ตัด semantic paths ออกเพื่อดูประโยชน์จาก adjacency อย่างเดียว.", ""])
    for baseline in ("vector4", "vector8", "adjacent4_plus4"):
        lines.append(f"- Graph เทียบ {baseline}: recall ดีขึ้น {len(summary[f'graph_vs_{baseline}_improved'])} ข้อ / แย่ลง {len(summary[f'graph_vs_{baseline}_regressed'])} ข้อ")
    lines.extend(["", "## แยกประเภท", "", "| ประเภท | ข้อมี gold | Vector4 recall | Vector8 recall | Graph recall |", "| --- | ---: | ---: | ---: | ---: |"])
    for category, group in result["by_category"].items():
        values = [group["variants"][v]["mean_recall"] for v in ("vector4", "vector8", "graph4_plus4")]
        lines.append(f"| {category} | {group['answerable_with_gold']} | " + " | ".join("N/A" if v is None else f"{v:.2%}" for v in values) + " |")
    lines.extend(["", "## รายข้อ (รายละเอียด paths/หลักฐานอยู่ใน results.json)", "", "| ข้อ | ประเภท | Vector4 | Vector8 | Graph | เพิ่มจากกราฟ |", "| --- | --- | ---: | ---: | ---: | --- |"])
    for row in result["rows"]:
        values = [row["variants"][v]["metrics"]["recall"] for v in ("vector4", "vector8", "graph4_plus4")]
        lines.append(f"| {row['question_id']} | {row['category']} | " + " | ".join("N/A" if v is None else f"{v:.0%}" for v in values)
                     + " | " + ", ".join(row["variants"]["graph4_plus4"]["chunk_ids"][4:]) + " |")
    lines.extend(["", "## ข้อจำกัด", "",
        "- นี่คือ cached-seed replay ไม่ใช่ CPE embedding benchmark ใหม่ หรือความเร็ว query Neo4j จริง.",
        "- วัด chunk retrieval ไม่ได้วัดความถูกต้องของ Fact/ความครบทุกความหมาย/คุณภาพคำตอบ LLM.",
        "- ข้อ unanswerable ไม่มี gold ไม่ใส่ recall=0; การพบ context ไม่ใช่การตอบผิดหรือปฏิเสธถูก.",
        "- กราฟเดิมเดินได้ภายใน document version เดียว ไม่ได้แก้การค้นข้ามเอกสารที่ Vector seed หาไม่พบ.",
        "- ไม่อ่าน gold_answer/key_facts มาเลือกผล; ทั้งคลังยัง PENDING, retrieval ปิด, ไม่มี semantic approval.",
        "- Recall เทียบ gold ที่ระบุเท่านั้น; chunk ที่ไม่อยู่ใน gold อาจเกี่ยวข้อง ต้องตรวจ source ก่อนสรุปว่าเป็น noise.",
        f"- API calls/tokens เพิ่ม 0/0; wall time {result['wall_seconds']:.3f}s รวมตรวจ snapshot และ replay ในเครื่อง.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/eval_311026.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output directory to preserve prior results")
    result = evaluate(args.export, args.baseline, args.dataset)
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "RESULTS.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"], "path_kinds": result["path_kinds"],
                      "wall_seconds": result["wall_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
