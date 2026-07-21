# MOD-SA Development Guide

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run backend:

```bash
uvicorn main:app --reload
```

Default:

```
http://127.0.0.1:8000
```

---

# Environment Configuration

Example:

```env
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=

EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=

CHROMA_DIR=storage/chroma
CHROMA_COLLECTION=modsa_kmutt

RAG_SOURCE_PATHS=storage/chunks
```

---

# Adding New Knowledge Data

Process:

```
Raw Documents
      |
      v
Chunk Preparation
      |
      v
storage/chunks
      |
      v
/reindex
```

Do not manually edit Chroma files.

---

# Adding New API Endpoint

1. Create route file:

```
api/example.py
```

1. Create schema:

```
schemas/example.py
```

1. Add business logic:

```
services/example_service.py
```

1. Register router in:

```
main.py
```

---

# Debugging Checklist

## No Answer

Check:

1. Are documents indexed?
2. Does Chroma contain vectors?
3. Is retrieval returning documents?
4. Is the prompt receiving context?

---

## Wrong Answer

Check:

1. Chunk quality.
2. Retrieval k value.
3. Metadata.
4. Prompt constraints.

---

## Slow Response

Check:

1. Retrieval size.
2. LLM latency.
3. Embedding provider.
4. Repeated initialization.

---

# Deployment Checklist

Before deployment:

* Remove debug code.
* Verify environment variables.
* Confirm Chroma persistence path.
* Run health check.
* Test sample questions.
