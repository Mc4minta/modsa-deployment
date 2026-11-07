# Pinned to specific Debian Bookworm slim Python 3.12 release
FROM python:3.12.8-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Bake data/chunks into the image (accessible at /app/data/chunks)
COPY data/chunks ./data/chunks

# Explicit numeric UID/GID (10001) for unprivileged appuser so host bind mounts
# (e.g. ./data/chroma -> /app/chroma_db) can be chowned predictably on the host VM
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd -g ${APP_GID} appuser \
    && useradd -u ${APP_UID} -g appuser --create-home appuser \
    && mkdir -p /app/chroma_db \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# start-period set to 600s because startup ingestion runs during FastAPI lifespan
# before the server begins listening. On a fresh index, embedding ~253 chunks
# via an external API can take several minutes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Note: Keep a single Uvicorn worker process. Embedded ChromaDB uses SQLite and local
# disk persistence; running multiple worker processes causes concurrent lifespan
# ingestion and database write races that corrupt SQLite and manifest state.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
