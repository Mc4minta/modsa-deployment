# Deployment reference

The filename is historical. This document no longer promises a free plan, fixed cold-start time, or provider/model availability. No remote deployment is performed by following the local graph quick start.

## Sources of truth

- [Backend configuration](../backend/README.md), [Dockerfile](../backend/Dockerfile), [Render configuration](../render.yml)
- [Frontend setup](../frontend/README.md)
- [Graph-only setup](../graph/QUICKSTART.md)

## Backend

Build context must be the repository root; Dockerfile is backend/Dockerfile. It copies backend/ and data/chunks/ into the image. The current render.yml uses /app/data/chunks; local Compose mounts sources at /app/storage/chunks. Neither uses datasets/ or a legacy backend folder.

Set real LLM/embedding credentials for the selected providers, model tags supported by the configured endpoint, CORS_ORIGINS, and a private ADMIN_API_KEY. Check the provider account's availability and costs before deploying; the local Ollama gateway is not accessible from a remote host via localhost.

GET /health returns200 only after nonempty ingestion succeeds;503 means the service is not ready. Startup can take time because it indexes sources. Persist CHROMA_DIR if the chosen hosting setup supports storage. Otherwise expect indexing after storage loss; no timing or pricing guarantee is implied.

## Frontend

Build from frontend/ with npm ci and npm run build, output dist/. VITE_API_URL is the backend HTTPS URL. Add the resulting frontend origins to backend CORS_ORIGINS. Test a real browser request and grounded answer after deployment; static builds alone do not verify the integration.

## Graph

graph/compose.yaml is a separate local Neo4j pilot. It does not deploy the chatbot or enable Hybrid in /chat/ask. Do not expose its local-only database configuration as a production deployment.
