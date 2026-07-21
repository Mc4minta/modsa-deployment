# MOD-SA Backend Architecture

## Overview

MOD-SA is a FastAPI-based RAG chatbot backend designed for KMUTT Student Affairs knowledge retrieval.

The system converts university documents into searchable embeddings and generates answers using retrieved context.

---

# Directory Structure

```
backend/

├── main.py
├── config.py

├── api/
│   ├── chat.py
│   ├── health.py
│   └── admin.py

├── core/
│   ├── llm.py
│   ├── embeddings.py
│   └── vectorstore.py

├── services/
│   ├── rag_service.py
│   ├── ingestion_service.py
│   └── retrieval_service.py

├── pipeline/
│   ├── loaders.py
│   ├── chunking.py
│   └── manifest.py

├── prompts/
│   └── rag_prompt.py

├── schemas/
│   └── chat.py

├── database/
│   └── chroma.py

├── models/
│   └── document.py

├── storage/
│   ├── chunks/
│   └── chroma/
```

---

# Component Responsibilities

## main.py

Application entry point.

Responsibilities:

* Create FastAPI instance.
* Register routers.
* Configure application lifecycle.

---

## API

Handles HTTP communication.

Example:

```
POST /ask
POST /reindex
GET /health
```

No business logic should exist here.

---

## Services

Contains application workflows.

### RAG Service

Flow:

```
Question
 ↓
Retrieve documents
 ↓
Build prompt
 ↓
Call LLM
 ↓
Return answer + sources
```

---

### Ingestion Service

Flow:

```
Source files
 ↓
Load documents
 ↓
Chunk documents
 ↓
Generate embeddings
 ↓
Store in Chroma
```

---

# Data Flow

## Indexing

```
Documents
   |
   v
Loader
   |
   v
Chunking
   |
   v
Embedding Model
   |
   v
Chroma Vector Database
```

---

## Question Answering

```
User Question
      |
      v
Retriever
      |
      v
Relevant Chunks
      |
      v
Prompt Builder
      |
      v
LLM
      |
      v
Answer + Sources
```

---

# Design Principles

## Single Responsibility

Each module should have one reason to change.

## Dependency Direction

Higher-level logic depends on lower-level utilities.

Infrastructure should not control application logic.

## Configuration Driven

Environment variables control:

* LLM provider.
* Embedding provider.
* Chroma location.
* Retrieval parameters.
