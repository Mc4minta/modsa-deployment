"""One fixed offline dev experiment: Vector4 + lexical Entity/Fact entry points.

First-stage TF-IDF retrieval, not a reranker or production policy service.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import time
import unicodedata

import retrieve
from sklearn import __version__ as sklearn_version
from sklearn.feature_extraction.text import TfidfVectorizer

METHOD = {"version": "direct-entity-fact-lexical-v1", "analyzer": "char", "ngram_range": [3, 5],
          "sublinear_tf": True, "norm": "l2", "seed_count": 4, "addition_limit": 4,
          "chunk_aggregation": "max_positive_record_cosine", "filters": False, "reranker": False}
VARIANTS = ("vector4", "vector8", "old_graph4_plus4", "chunk_lexical4_plus4", "entity_fact4_plus4")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def fact_records(graph) -> list[dict]:
    records = []
    for key, node in sorted(graph.nodes.items()):
        if node["label"] != "Fact":
            continue
        subjects, about_ids, targets = [], [], []
        for edge_id, edge in graph.outgoing[key]:
            if edge["type"] == "ABOUT":
                subject = graph.nodes[edge["target"]]
                subjects.extend(str(v) for k, v in subject["properties"].items()
                                if k in {"name", "scope_text", "academic_year_be", "round", "degree"} and v is not None)
                if subject["label"] == "Offering":
                    for _, parent in graph.incoming[edge["target"]]:
                        if parent["type"] == "HAS_OFFERING":
                            subjects.append(graph.nodes[parent["source"]]["properties"]["name"])
                about_ids.append(edge_id)
            elif edge["type"] == "SUPPORTED_BY":
                chunk = graph.chunks[edge["target"]]
                if edge["properties"]["quote"] not in chunk.page_content:
                    raise ValueError("Evidence drift")
                targets.append({"chunk_node_id": edge["target"], "support_edge_id": edge_id,
                                "quote": edge["properties"]["quote"]})
        if not about_ids or not targets:
            raise ValueError("Searchable Fact must have subjects and source evidence")
        fields = [str(v) for k, v in node["properties"].items()
                  if k in {"predicate", "scope_text", "raw_text", "value_text"} and v is not None]
        text = "\n".join(dict.fromkeys(subjects + fields))
        records.append({"record_id": key, "text": text, "kind": "entity_fact",
                        "about_edge_ids": about_ids, "targets": targets})
    return records


class LexicalIndex:
    def __init__(self, graph, records: list[dict]):
        if not records or len({r["record_id"] for r in records}) != len(records):
            raise ValueError("Index requires unique nonempty records")
        self.graph, self.records = graph, records
        self.vectorizer = TfidfVectorizer(analyzer=METHOD["analyzer"], ngram_range=tuple(METHOD["ngram_range"]),
            sublinear_tf=METHOD["sublinear_tf"], norm=METHOD["norm"], lowercase=False)
        self.matrix = self.vectorizer.fit_transform([normalize(r["text"]) for r in records])

    def search(self, question: str, seeds: list, *, limit: int = 4) -> tuple[list, list[dict]]:
        if not isinstance(question, str) or type(limit) is not int or not 0 <= limit <= 20:
            raise ValueError("Question/limit invalid")
        if any(self.graph.anchor(doc) is None for doc in seeds):
            raise ValueError("Stale seed cannot bridge to snapshot")
        if not question.strip() or not limit:
            return [], []
        scores = (self.matrix @ self.vectorizer.transform([normalize(question)]).T).toarray().ravel()
        excluded = {self.graph.anchor(doc) for doc in seeds}
        chunks = {}
        for index, record in enumerate(self.records):
            score = float(scores[index])
            if score <= 0:
                continue
            for target in record["targets"]:
                key = target["chunk_node_id"]
                if key in excluded:
                    continue
                if key not in self.graph.chunks:
                    raise ValueError("Search record targets unknown chunk")
                trace = {"record_id": record["record_id"], "kind": record["kind"], "score": score,
                         "about_edge_ids": record.get("about_edge_ids", []), **target}
                if key not in chunks or (-score, record["record_id"]) < (-chunks[key]["score"], chunks[key]["record_id"]):
                    chunks[key] = trace
        selected = sorted(chunks, key=lambda key: (-chunks[key]["score"], key))[:limit]
        return [self.graph.chunks[key] for key in selected], [chunks[key] for key in selected]


def summary(rows: list[dict]) -> dict:
    eligible = [r for r in rows if r["answerable"] and r["gold_chunk_ids"]]
    result = {"question_count": len(rows), "scored_questions": len(eligible), "variants": {}}
    for variant in VARIANTS:
        metrics = [r["variants"][variant]["metrics"] for r in eligible]
        result["variants"][variant] = {
            "mean_recall": statistics.mean(m["recall"] for m in metrics) if metrics else None,
            "complete": sum(m["complete"] for m in metrics),
            "mean_precision_at_budget": statistics.mean(m["precision_at_budget"] for m in metrics) if metrics else None,
            "mean_context_chunks": statistics.mean(r["variants"][variant]["metrics"]["context_chunks"] for r in rows),
            "mean_context_characters": statistics.mean(r["variants"][variant]["context_characters"] for r in rows)}
    for control in ("vector8", "old_graph4_plus4", "chunk_lexical4_plus4"):
        for name, sign in (("improved", 1), ("regressed", -1)):
            result[f"entity_fact_vs_{control}_{name}"] = [r["question_id"] for r in eligible if sign * (
                r["variants"]["entity_fact4_plus4"]["metrics"]["recall"] - r["variants"][control]["metrics"]["recall"]) > 0]
    return result


def evaluate(export_path: Path, baseline_path: Path) -> dict:
    started = time.perf_counter()
    verified = retrieve.read(export_path.with_name("load_verification.json"))
    if retrieve.file_hash(export_path) != verified["graph_sha256"]:
        raise ValueError("Export changed since readback")
    graph, _, by_chunk = retrieve.snapshot_graph(retrieve.read(export_path), verified)
    graph_before = retrieve.fingerprint({"nodes": graph.nodes, "edges": graph.edges})
    t0 = time.perf_counter()
    records = fact_records(graph)
    fact_index = LexicalIndex(graph, records)
    chunk_index = LexicalIndex(graph, [{"record_id": key, "text": doc.page_content, "kind": "chunk_lexical",
        "targets": [{"chunk_node_id": key}]} for key, doc in sorted(graph.chunks.items())])
    index_seconds = time.perf_counter() - t0
    dataset_path = retrieve.ROOT / "data/evaluation/eval_311026.json"
    questions = [q for q in retrieve.read(dataset_path) if q["split"] == "dev"]
    raw = [json.loads(line) for line in baseline_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    baseline = {r["question_id"]: r for r in raw}
    if len(raw) != len(baseline) or len({q["question_id"] for q in questions}) != len(questions):
        raise ValueError("Duplicate benchmark IDs")
    rows = []
    for q in questions:
        seeds = retrieve.replay_seeds(q, baseline[q["question_id"]], by_chunk)
        old, old_paths = graph.expand(seeds[:4], limit=4)
        variants = {"vector4": seeds[:4], "vector8": seeds[:8], "old_graph4_plus4": seeds[:4] + old}
        traces, query_seconds = {"old_graph4_plus4": old_paths}, {}
        # Retrieval sees only the question and exact seeds, never gold/answer/category.
        for name, index in (("chunk_lexical4_plus4", chunk_index), ("entity_fact4_plus4", fact_index)):
            t0 = time.perf_counter()
            additions, trace = index.search(q["question"], seeds[:4], limit=4)
            query_seconds[name] = time.perf_counter() - t0
            variants[name], traces[name] = seeds[:4] + additions, trace
        scored = {}
        for name, docs in variants.items():
            ids = [doc.metadata["chunk_id"] for doc in docs]
            if ids[:4] != [d.metadata["chunk_id"] for d in seeds[:4]] or len(ids) != len(set(ids)) or len(ids) > 8:
                raise ValueError("Context budget/order/identity violated")
            scored[name] = {"chunk_ids": ids, "context_characters": sum(len(d.page_content) for d in docs),
                "metrics": retrieve.metrics(ids, q["gold_chunk_ids"], 4 if name == "vector4" else 8)}
        rows.append({k: q[k] for k in ("question_id", "question", "category", "answerable", "gold_chunk_ids")}
                    | {"variants": scored, "traces": traces, "query_seconds": query_seconds})
    if graph_before != retrieve.fingerprint({"nodes": graph.nodes, "edges": graph.edges}):
        raise ValueError("Experiment mutated graph")
    return {"status": "OFFLINE_DEV_LEXICAL_ENTRY_POINT_EXPERIMENT_NOT_PRODUCTION", "method": METHOD,
        "created_at": datetime.now(timezone.utc).isoformat(), "sklearn_version": sklearn_version,
        "pins": {"export_sha256": retrieve.file_hash(export_path), "baseline_sha256": retrieve.file_hash(baseline_path),
            "dataset_sha256": retrieve.file_hash(dataset_path), "script_sha256": retrieve.file_hash(Path(__file__)),
            "adapter_sha256": retrieve.file_hash(Path(retrieve.__file__)),
            "walker_sha256": retrieve.file_hash(retrieve.ROOT / "backend/services/graph_service.py")},
        "fact_records": len(records), "chunk_records": len(graph.chunks), "index_seconds": index_seconds,
        "summary": summary(rows), "by_category": {c: summary([r for r in rows if r["category"] == c])
            for c in sorted({r["category"] for r in rows})}, "rows": rows,
        "new_api_calls": 0, "new_tokens": 0, "database_writes": False, "graph_unchanged": True,
        "hybrid_enabled": False, "test_split_used": False, "wall_seconds": time.perf_counter() - started}


def report(result: dict) -> str:
    lines = ["# ทดลองทางเข้าค้น Entity/Fact โดยตรง — dev", "",
        "ค่าทดลองกำหนดก่อนดูคะแนน: char TF-IDF3–5grams, sublinear TF, L2/cosine; ไม่จูนด้วยgold.",
        "Fact recordsประกอบด้วยชื่อ/scopeของABOUT subjects และpredicate/scope/raw_text/value_textของFactเดิม.",
        "ค้นทั้งคลังแล้วคืนSUPPORTED_BY chunksเดิม: เป็นการค้นแยกแต่ละsource/version ไม่ใช่mergeidentityหรือยืนยันว่าทุกเอกสารใช้ร่วมกันได้.",
        "เก็บVector4เดิม เพิ่มไม่เกิน4; ไม่มีreranker/LLM/embedding API. ใช้chunk lexical searchด้วยวิธีเดียวกันเป็นcontrol.", "",
        "| วิธี | Recall | ครบทุกgold | Precisionตามงบ | Contextเฉลี่ย | อักขระเฉลี่ย |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, m in result["summary"]["variants"].items():
        lines.append(f"| {name} | {m['mean_recall']:.2%} | {m['complete']}/{result['summary']['scored_questions']} | {m['mean_precision_at_budget']:.2%} | {m['mean_context_chunks']:.2f} | {m['mean_context_characters']:.0f} |")
    lines.extend(["", "## คู่เปรียบเทียบ", ""])
    for control in ("vector8", "old_graph4_plus4", "chunk_lexical4_plus4"):
        s = result["summary"]
        lines.append(f"- Entity/Factเทียบ{control}: ดีขึ้น {len(s[f'entity_fact_vs_{control}_improved'])} ข้อ / แย่ลง {len(s[f'entity_fact_vs_{control}_regressed'])} ข้อ; IDsทั้งหมดอยู่ในresults.json")
    lines.extend(["", "## รายข้อ", "", "| ข้อ | Vector8 | กราฟเดิม | Chunk lexical | Entity/Fact |", "| --- | ---: | ---: | ---: | ---: |"])
    for row in result["rows"]:
        values = [row["variants"][v]["metrics"]["recall"] for v in VARIANTS[1:]]
        lines.append(f"| {row['question_id']} | " + " | ".join("N/A" if v is None else f"{v:.1%}" for v in values) + " |")
    lines.extend(["", "## ข้อจำกัด", "",
        "- dev34ข้อ:26ข้อมีgold,8unanswerableเป็นN/A. test76ข้อยังไม่รัน; ไม่ใช่การประเมินคุณภาพคำตอบ.",
        "- เป็นfirst-stage lexical retrieval ไม่ใช่entity linkingเชิงความหมาย/LLM reasoning และไม่รับรองfact/policyถูกต้อง.",
        "- ถ้าดีกว่ากราฟเดิมแต่ไม่ดีกว่าchunk lexical ยังแยกไม่ได้ว่าโครงสร้างกราฟให้ประโยชน์เหนือช่องทางค้นข้อความ.",
        "- เก็บปี/รุ่น/หลักฐานเดิม ไม่filterความใช้ได้ในปัจจุบัน; การคืนหลายเอกสารไม่เท่ากับยืนยันว่าทุน/เกณฑ์เดียวกัน.",
        "- งบเท่ากันในจำนวนchunksสูงสุด ไม่ใช่tokens; รายงานอักขระเพื่อเห็นขนาดcontext ไม่ประมาณbillable tokens.",
        "- ไม่มีการเรียกCPE/สกัดใหม่/merge nodes/DBwrites/เปิดHybrid; no-positive-matchคืนว่าง ไม่เติมแบบเดา.",
        f"- API calls/tokensเพิ่ม0/0; build indexes {result['index_seconds']:.3f}s; wall {result['wall_seconds']:.3f}s (ไม่ใช่production latency).", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve prior experiment; choose new output directory")
    result = evaluate(args.export, args.baseline)
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "RESULTS.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({"summary": result["summary"], "fact_records": result["fact_records"],
                      "index_seconds": result["index_seconds"], "wall_seconds": result["wall_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
