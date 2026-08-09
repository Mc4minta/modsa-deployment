# Evaluation Data

This folder contains all dataset files for the evaluation benchmark.

## Structure

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
└── final/                       ← USE THIS for evaluation
    ├── evaluation_academic_calendar.json    (39 questions)
    ├── evaluation_academic_rules.json       (37 questions)
    ├── evaluation_fees.json                 (46 questions)
    ├── evaluation_others.json               (30 questions)
    ├── evaluation_registration.json         (61 questions)
    └── evaluation_scholarship.json          (39 questions)
```

## Which Folder to Use

| Folder        | When to use                                                                              |
| ------------- | ---------------------------------------------------------------------------------------- |
| `final/`      | **Evaluation benchmark.** Clean, deduplicated, renumbered. This is the standard dataset. |
| `merged_raw/` | Audit/debug. See duplicates, gold_chunk overlaps, raw merged data.                       |
| `raw/`        | Never edit. Original source files from annotators.                                       |

## Question Schema

Every question across all files follows this schema:

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

## Cautions for Evaluators

1. **Use `final/` only** — The other folders are intermediate/audit. Do not evaluate against `merged_raw/` or `raw/`.
2. **Thai language** — All questions and answers are in Thai. Ensure your evaluation pipeline handles Thai text correctly.
3. **`answer_must_contain` is a list** — A correct answer should contain ALL listed phrases, not just one.
4. **`gold_chunk` overlap** — Some questions from both annotators target the same chunk. Both are valid — different wording, possibly different intent.
5. **No `question_id` in `merged_raw/`** — IDs are only generated in `final/`. The merged files intentionally strip them.
6. **`answerable: false` not present** — All current questions are answerable. If future annotator rounds add unanswerable questions, they will appear here.
