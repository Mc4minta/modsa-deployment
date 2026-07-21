# MOD-SA Backend Agent Skill

## Purpose

This skill defines the development rules and architectural constraints for the MOD-SA RAG backend.

The backend provides a Retrieval-Augmented Generation (RAG) chatbot for KMUTT Student Affairs information.

## Project Context

MOD-SA is a knowledge assistant that answers student-related questions using:

* FastAPI backend
* LangChain orchestration
* Chroma vector database
* LLM API compatible providers
* Preprocessed knowledge chunks
* Retrieval-based answering

Main responsibilities:

1. Load and index KMUTT knowledge documents.
2. Retrieve relevant information.
3. Generate grounded answers.
4. Provide source references.

---

# Architecture Rules

## Separation of Responsibilities

Follow this dependency direction:

```
API
 ↓
Services
 ↓
Core / Pipeline
 ↓
External Systems
```

Do not mix layers.

---

## API Layer

Location:

```
api/
```

Responsibilities:

* Define routes.
* Validate requests.
* Return responses.

Must NOT contain:

* LLM initialization.
* Vector database logic.
* Document processing.
* Prompt construction.

---

## Service Layer

Location:

```
services/
```

Responsibilities:

* Implement application workflows.
* Coordinate multiple components.

Examples:

```
rag_service.py
ingestion_service.py
```

Services decide what happens.

They should not know FastAPI details.

---

## Core Layer

Location:

```
core/
```

Responsibilities:

Create reusable infrastructure clients.

Examples:

```
llm.py
embeddings.py
vectorstore.py
```

Contains:

* OpenAI compatible client creation.
* Ollama embedding setup.
* Chroma initialization.

---

## Pipeline Layer

Location:

```
pipeline/
```

Responsibilities:

Data preparation.

Examples:

```
loaders.py
chunking.py
manifest.py
```

Contains:

* File discovery.
* Document loading.
* Chunk processing.
* Dataset tracking.

---

# Code Rules

## Avoid Large Files

A file should have one main responsibility.

Avoid files containing:

* API routes
* Database access
* Business logic
* External clients

at the same time.

---

## Import Rules

Preferred:

```
api
 └── services

services
 └── core
 └── pipeline

core
 └── external libraries
```

Avoid:

```
core -> api
pipeline -> services
```

---

# RAG Rules

Answers must:

* Use retrieved context only.
* Avoid hallucinating unsupported information.
* Mention insufficient information when retrieval is weak.
* Preserve source metadata.

---

# Modification Guidelines

Before adding features:

1. Identify the correct layer.
2. Reuse existing services.
3. Avoid adding logic to API files.
4. Keep configuration centralized.

---

# Testing Checklist

After changes:

* API starts successfully.
* Health endpoint works.
* Retrieval still returns documents.
* RAG response includes sources.
* Reindex operation works.