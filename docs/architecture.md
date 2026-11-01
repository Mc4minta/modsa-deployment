# MOD-SA architecture

- Source data: data/chunks/
- Active API: backend/ — API → services → core/pipeline
- Chat runtime: Vector retrieval in Chroma → grounded LLM answer → sources
- Graph pilot: graph/ — frozen inputs → extraction replay → validated graph export → isolated Neo4j
- Frontend: frontend/ — React/TypeScript/Vite client

The graph build does not start the API, reindex Chroma, or enable Hybrid automatically. The ignored research archive is not required.

Start at [root README](../README.md), [backend architecture](backend-structure.md), or [graph quick start](../graph/QUICKSTART.md).
