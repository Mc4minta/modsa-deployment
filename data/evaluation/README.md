# Evaluation Data

This folder contains the shared Naive/Graph answer-quality benchmark and its legacy source datasets.

## Active Naive vs Graph benchmark

Use **`eval_311026.json`**, the same dataset used by the friend's Gemma baseline in `min_011126_202852/eval_runs/base/run.json`. Confirmed against that project's `data/evaluation/eval_311026.json`: parsed JSON is identical; no questions, answers, IDs or split assignments were changed.

- 110 questions: 30 single-hop, 35 multi-hop, 20 global and 25 unanswerable.
- Preserve the existing split: **dev 34 / test 76**. Develop on dev; use test only after freezing the setup.
- Fields include `gold_chunk_ids`, `gold_answer`, `key_facts`, `exact_tokens`, `answerable`, `category` and `split`.
- Do not substitute `eval.json`, `final/*.json` or `graph/data/inputs/questions.json`; those are different datasets/schemas.
- The old Gemma outputs remain historical results. The planned CPE comparison must use the same benchmark for both Naive and Graph.

## Graph files moved

ชุดสร้างกราฟอยู่ [graph/](../../graph/README.md) แล้ว. ผลทดลอง schema/โมเดล/คำตอบเดิมเก็บเฉพาะเครื่องที่ `.local/graph-rag-research/data/` และไม่เข้า Git. โฟลเดอร์นี้คงเฉพาะ benchmark เดิม

Sections below describe the **legacy benchmark** (`raw/`, `merged_raw/`, `final/`), not the active 110-question benchmark or the GraphRAG pilot schema.

## Legacy structure

```txt
evaluation/
├── raw/                         ← Source data (extracted from ZIP)
│   ├── personA-M/               ← Annotator A
│   │   ├── evaluation_academic_calendar.json    (20 questions)
│   │   ├── evaluation_academic_rules.json       (20 questions)
│   │   ├── evaluation_fees.json                 (30 questions)
│   │   ├── evaluation_others.json               (10 questions)
│   │   ├── evaluation_registration.json         (20 questions)
│   │   └── evaluation_scholarship.json          (20 questions)
│   └── personB-W/               ← Annotator B
│       ├── evaluation_academic_calendar.json    (20 questions)
│       ├── evaluation_academic_rules.json       (19 questions)
│       ├── evaluation_fees.json                 (16 questions)
│       ├── evaluation_others.json               (20 questions)
│       ├── evaluation_registration.json         (42 questions)
│       └── evaluation_scholarship.json          (20 questions)
│
├── merged_raw/                  ← Phase 1 output (pre-dedup)
│   ├── evaluation_*.json        ← Concatenated arrays (257 total)
│   ├── duplicate_report.json    ← Detected duplicate pairs
│   └── gold_chunk_grouped.json  ← All questions sorted by gold_chunk
│
└── final/                       ← Legacy finalized dataset (not the active CPE benchmark)
    ├── evaluation_academic_calendar.json    (39 questions)
    ├── evaluation_academic_rules.json       (37 questions)
    ├── evaluation_fees.json                 (46 questions)
    ├── evaluation_others.json               (30 questions)
    ├── evaluation_registration.json         (61 questions)
    └── evaluation_scholarship.json          (39 questions)
```

## Legacy folder roles

| Folder        | When to use                                                                              |
| ------------- | ---------------------------------------------------------------------------------------- |
| `final/`      | Legacy clean, deduplicated dataset. Not the active Naive/Graph benchmark. |
| `merged_raw/` | Audit/debug. See duplicates, gold_chunk overlaps, raw merged data.                       |
| `raw/`        | Never edit. Original source files from annotators.                                       |

## Legacy question schema

Legacy questions follow this schema; the active `eval_311026.json` uses the fields listed above. `../../graph/data/inputs/questions.json` uses its own evidence-backed development schema:

```json
{
    "question_id": "academic_calendar-q001",
    "question": "The evaluation question in Thai",
    "category": "academic_calendar",
    "gold_doc": "Source document identifier",
    "gold_chunk": "Specific chunk ID within the document",
    "answer_must_contain": ["Required answer phrase 1", "Required answer phrase 2"],
    "answerable": true
}
```

### Field Descriptions

| Field                 | Description                                                                  |
| --------------------- | ---------------------------------------------------------------------------- |
| `question_id`         | Unique ID. Format: `{category}-q{NNN}`. Regenerated during finalization.     |
| `question`            | The evaluation question (Thai language).                                     |
| `category`            | Knowledge domain. One of 6 categories.                                       |
| `gold_doc`            | Source document the answer comes from.                                       |
| `gold_chunk`          | Specific chunk/section within the source document. Used for dedup detection. |
| `answer_must_contain` | Phrases that must appear in a correct answer.                                |
| `answerable`          | `true` = question has a definite answer in the documents.                    |

## Cautions for legacy data

1. **For the current Naive/Graph comparison use `eval_311026.json`**, not these legacy folders. The local archived GraphRAG pilot is for development, not an approved replacement benchmark.
2. **Thai language** — All questions and answers are in Thai. Ensure your evaluation pipeline handles Thai text correctly.
3. **`answer_must_contain` is a list** — A correct answer should contain ALL listed phrases, not just one.
4. **`gold_chunk` overlap** — Some questions from both annotators target the same chunk. Both are valid — different wording, possibly different intent.
5. **No `question_id` in `merged_raw/`** — IDs are only generated in `final/`. The merged files intentionally strip them.
6. **Legacy folders have no `answerable: false`** — The active `eval_311026.json` does include 25 unanswerable questions.
