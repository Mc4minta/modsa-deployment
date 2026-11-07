# MOD-SA Single-VM Deployment Runbook

This runbook provides step-by-step instructions for deploying and operating the **MOD-SA** (KMUTT Student Affairs RAG Assistant) on a single Ubuntu 24.04 LTS virtual machine using Docker Compose, Nginx reverse proxy, and Cloudflare Tunnel.

---

## 1. Prerequisites & Institutional Approval Gate

> [!CAUTION]
> **KMUTT Institutional Approval Gate**
> Before enabling or starting any outbound Cloudflare Tunnel (`--profile quick` or `--profile named`), formal authorization must be obtained in compliance with KMUTT IT and network security policies.

- [ ] **Approval Gate**: Obtained formal permission from KMUTT Computer Center / Student Affairs for public hosting and outbound Cloudflare tunnel traffic.
- [ ] **Target VM Specifications**:
  - **OS**: Clean installation of Ubuntu 24.04 LTS (Noble Numbat).
  - **CPU & RAM**: Recommended 16 vCPU, 16 GB RAM (minimum 4 vCPU, 8 GB RAM).
  - **Disk**: 50+ GB SSD storage with at least 20 GB free space on `/var`.
  - **Network**: Outbound HTTPS (port 443) access to:
    - Docker Hub & Debian/Ubuntu apt repositories
    - GitHub (`github.com`)
    - Cloudflare Edge (`*.cloudflare.com`, `*.trycloudflare.com`)
    - LLM provider API (OpenAI, Ollama Cloud, or custom endpoint)
    - Embedding provider API (Hugging Face Inference or OpenAI)
  - **Inbound Ports**: No public inbound ports required! Access is brokered entirely via outbound Cloudflare Tunnel (or campus VPN during local testing).

---

## 2. Install Docker Engine on Ubuntu 24.04

Install the official Docker Engine and Docker Compose plugin using Docker's official apt repository:

```bash
# 1. Update existing packages
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# 2. Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Set up the Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker packages
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Add current user to docker group (re-login required after this)
sudo usermod -aG docker $USER
```

Verify the installation:

```bash
docker --version
docker compose version
```

---

## 3. First-Time Setup

### 3.1 Clone Repository and Checkout Branch

```bash
cd /opt
sudo git clone https://github.com/Mc4minta/modsa-deployment.git modsa
sudo chown -R $USER:$USER /opt/modsa
cd /opt/modsa
git checkout modsa-vm
```

### 3.2 Configure Environment Variables

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` using your preferred editor (`nano .env` or `vim .env`):

```bash
# 1. LLM Generation
LLM_BASE_URL="https://api.openai.com/v1"
LLM_API_KEY="sk-proj-..."
LLM_MODEL="gpt-4o-mini"
LLM_TIMEOUT="30.0"
LLM_MAX_RETRIES="1"  # Keeps worst-case retry time well under Cloudflare's 100s timeout

# 2. Embeddings (Choose ONE provider)
# For OpenAI embeddings:
EMBEDDING_PROVIDER="openai"
EMBEDDING_BASE_URL="https://api.openai.com/v1"
EMBEDDING_API_KEY="sk-proj-..."
EMBEDDING_MODEL="text-embedding-3-small"
EMBEDDING_TIMEOUT="30.0"
EMBEDDING_MAX_RETRIES="1"

# Or for Hugging Face Inference API:
# EMBEDDING_PROVIDER="huggingface"
# EMBEDDING_BASE_URL="https://api-inference.huggingface.co"
# EMBEDDING_API_KEY="hf_..."
# EMBEDDING_MODEL="BAAI/bge-m3"

# 3. Security & Admin
ADMIN_API_KEY="$(openssl rand -hex 32)"
```

### 3.3 Set Up ChromaDB Persistence Directory

The backend container runs as unprivileged user `appuser` with numeric `UID: 10001` and `GID: 10001`. The persistent host directory `./data/chroma` must be owned by this ID:

```bash
mkdir -p data/chroma
sudo chown -R 10001:10001 data/chroma
sudo chmod -R 750 data/chroma
```

---

## 4. Local Verification over VPN (Local Override)

Before opening any public tunnel, verify the entire application locally over the university network or VPN using the `docker-compose.local.yml` override:

```bash
# Start backend and nginx locally (exposes 127.0.0.1:8080:80)
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

> [!NOTE]
> **Understanding the Long First Boot (Cold Start)**
> On first startup, the backend lifespan handler detects an empty Chroma collection and embeds all 253 chunk documents via the configured external API.
> The backend health check has a `start_period: 600s` to allow this indexing to complete. Nginx waits for backend health before becoming healthy.
> Monitor progress with: `docker compose logs -f backend`. Once complete, you will see `Startup ingestion: {'status': 'indexed', 'documents': 253, ...}`.

### 4.1 Verification Checklist

Run these commands from the VM host (or over SSH/VPN):

- [ ] **1. Nginx health check (not proxied)**:
  ```bash
  curl -i http://127.0.0.1:8080/nginx-health
  # Expected: HTTP/1.1 200 OK, body: healthy
  ```

- [ ] **2. Backend health check (proxied via Nginx)**:
  ```bash
  curl -s http://127.0.0.1:8080/api/health
  # Expected: {"status":"ok","ingestion":{"status":"indexed",...}}
  ```

- [ ] **3. Chat question answering**:
  ```bash
  curl -s -X POST http://127.0.0.1:8080/api/chat/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"มีทุนการศึกษาอะไรบ้างสำหรับนักศึกษา"}'
  # Expected: 200 OK with {"answer":"...","sources":[...]}
  ```

- [ ] **4. Verify `/api/admin/reindex` returns 404 from Nginx**:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8080/api/admin/reindex
  # Expected: 404
  ```

- [ ] **5. Verify Swagger UI (`/docs`, `/redoc`, `/openapi.json`) are blocked**:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/docs
  # Expected: 200 (returns SPA index.html fallback, NOT Swagger UI documentation)
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/docs
  # Expected: 404
  ```

- [ ] **6. Verify ChromaDB persistence across restarts**:
  ```bash
  docker compose restart backend
  docker compose logs backend | tail -n 20
  # Expected: Lifespan matches source_manifest.json and reports:
  # Startup ingestion: {'status': 'skipped', 'reason': 'manifest matches existing collection', ...}
  # Boot completes in less than 2 seconds!
  ```

---

## 5. Starting Cloudflare Tunnel

### 5.1 Option A: Cloudflare Quick Tunnel (Preview / Testing)

Quick Tunnels provide an ephemeral `*.trycloudflare.com` domain with zero configuration required.

```bash
# Launch stack with quick profile
docker compose --profile quick up -d --build

# Retrieve assigned tunnel URL
docker compose logs cloudflared | grep -o 'https://[-a-zA-Z0-9.]*\.trycloudflare\.com' | head -n 1
```

### 5.2 Option B: Cloudflare Named Tunnel (Production / University Domain)

Named Tunnels bind to a permanent custom domain (e.g. `modsa.kmutt.ac.th`):

1. In Cloudflare Zero Trust Dashboard, navigate to **Networks** -> **Tunnels** -> **Create a Tunnel**.
2. Select **Cloudflared**, name the tunnel (e.g. `modsa-production`), and copy the tunnel token.
3. In Public Hostname settings, route `modsa.kmutt.ac.th` to HTTP service: `http://nginx:80`.
4. Add the token to `.env`:
   ```bash
   TUNNEL_TOKEN="eyJhIjoi..."
   ```
5. Launch the named tunnel:
   ```bash
   docker compose --profile named up -d --build
   ```

### 5.3 External Verification

From an outside machine (mobile phone on 5G or external network):

- [ ] Open the public tunnel URL in a browser. The React SPA should load instantly.
- [ ] Send a test query ("สอบถามเรื่องหอพัก"). Confirm response and sources render correctly.
- [ ] **Rate Limiting Test**: Send a rapid burst of 12 requests in 5 seconds to `/api/chat/ask`:
  ```bash
  for i in {1..12}; do
    curl -s -o /dev/null -w "%{http_code} " -X POST "https://<your-tunnel-url>/api/chat/ask" \
      -H "Content-Type: application/json" \
      -d '{"question":"ping"}'
  done
  echo ""
  # Expected output: 422/200 followed by several 429 responses
  ```

---

## 6. Routine Operations & Maintenance

### 6.1 Viewing Service Logs

```bash
# Follow Nginx access and error logs
docker compose logs -f nginx

# Follow Backend FastAPI application logs
docker compose logs -f backend

# Follow Cloudflare tunnel connection logs
docker compose logs -f cloudflared        # For Quick Tunnel
docker compose logs -f cloudflared-named  # For Named Tunnel
```

### 6.2 Updating Application Code

```bash
cd /opt/modsa
git pull origin modsa-vm
docker compose --profile quick up -d --build   # Or --profile named
```

### 6.3 Backup and Disaster Recovery

- **Create a Backup**:
  ```bash
  ./scripts/backup.sh
  ```
  Archives `./data/chroma` to `./backups/chroma_backup_<TIMESTAMP>.tar.gz` and prunes archives older than the 5 most recent.
  > [!IMPORTANT]
  > Copy backup archives off the VM to secure remote storage (SFTP, AWS S3, or institutional backup).

- **Restore from Backup**:
  ```bash
  ./scripts/restore.sh backups/chroma_backup_20261107_120000.tar.gz
  ```

- **Rebuild Index from Chunks (Reindex)**:
  ```bash
  ./scripts/reindex.sh
  ```
  Triggers a fresh re-embedding of all 253 JSON chunk documents from `/app/data/chunks`.

### 6.4 Resource Monitoring

```bash
# Monitor container CPU and memory usage
docker stats --no-stream

# Monitor host disk usage
df -h /opt/modsa/data/chroma
```

---

## 7. Troubleshooting Guide

| Issue | Symptoms | Probable Cause | Remediation |
|---|---|---|---|
| **Backend Crash Loop** | `docker compose ps` shows backend restarting constantly | Missing or invalid API key, or `EMBEDDING_PROVIDER=huggingface` without `EMBEDDING_API_KEY` | Inspect `docker compose logs backend`. Confirm required keys in `.env`. |
| **Permission Denied on Chroma** | `sqlite3.OperationalError: unable to open database file` | Host directory `./data/chroma` not owned by container user | Run `sudo chown -R 10001:10001 ./data/chroma && sudo chmod -R 750 ./data/chroma`. |
| **502 Bad Gateway from Nginx** | Browser shows `Bad gateway: backend service is currently unreachable` | Backend is still compiling index during first boot, or crashed | Check `docker compose logs backend`. Wait for startup ingestion to log `Startup ingestion: {'status': ...}`. |
| **504 Gateway Timeout** | Request hangs for ~95s and returns 504 | LLM or embedding provider taking longer than 95s (retries exceeded) | Set `LLM_MAX_RETRIES=1` and `EMBEDDING_MAX_RETRIES=1` in `.env` to prevent retry pileups. |
| **429 Too Many Requests** | Client receives `{"detail":"Too many requests..."}` | Per-IP limit (10 req/min) or global limit (60 req/min) exceeded | Wait 60 seconds. Tune `rate=10r/m` or `rate=60r/m` in `nginx/nginx.conf` if legitimately needed. |
| **Tunnel URL Changed** | Previous `trycloudflare.com` URL is unreachable | Quick Tunnel restarted, generating a new random subdomain | Check new URL with `docker compose logs cloudflared`. Migrate to Named Tunnel for permanent URL. |
| **Empty or Nonsensical Answers** | Chat returns blank answers or low similarity after changing model | Changed `EMBEDDING_MODEL` without rebuilding Chroma index | Run `./scripts/reindex.sh`. Vector store must be re-embedded when embedding dimension or model changes. |

---

## 8. Migration: Quick Tunnel to Named University Domain

When moving from pilot evaluation to production under `*.kmutt.ac.th`:

1. Request a DNS CNAME or Cloudflare Zone delegation from KMUTT Computer Center for your chosen domain (e.g. `modsa.kmutt.ac.th`).
2. Log into the Cloudflare Zero Trust dashboard and create a Named Tunnel.
3. Map the public hostname `modsa.kmutt.ac.th` to service `http://nginx:80`.
4. Set `TUNNEL_TOKEN="<your-token>"` in `/opt/modsa/.env`.
5. Switch Docker Compose profiles:
   ```bash
   # Stop quick tunnel
   docker compose --profile quick down

   # Start named tunnel
   docker compose --profile named up -d --build
   ```

---

## 9. Known Technical Limitations

1. **Cloudflare Quick Tunnels (`trycloudflare.com`)**:
   - Ephemeral subdomains change whenever the container restarts.
   - Cloudflare provides no uptime SLA for Quick Tunnels.
   - Enforces a concurrency threshold (approximately 200 concurrent requests).
2. **Cloudflare Edge Timeout (~100 Seconds)**:
   - Cloudflare terminates HTTP proxy connections that remain idle for 100 seconds (HTTP 524).
   - MOD-SA backend worst-case latency is: `(LLM_TIMEOUT x (LLM_MAX_RETRIES + 1)) + embedding time`.
   - With `LLM_TIMEOUT=30s` and `LLM_MAX_RETRIES=1`, worst-case is ~65s, fitting comfortably within the 100s window.
   - `nginx/nginx.conf` sets `proxy_read_timeout 95s` so Nginx fails fast and returns a clean JSON error before Cloudflare drops the TCP connection.

---

## 10. Security Architecture Summary

- **Network Isolation**: The backend container does NOT publish port 8000 to the host VM. It can only be reached over the private Docker network (`modsa_net`) by Nginx.
- **Strict Public URL Allowlist**: Nginx only routes `GET /api/health` and `POST /api/chat/ask`. All other routes (`/api/admin/*`, `/api/docs`, `/api/openapi.json`) return 404 Not Found.
- **Admin Isolation**: `POST /admin/reindex` cannot be accessed through the tunnel or Nginx; it can only be invoked internally via `scripts/reindex.sh` using container exec.
- **Error Sanitization**: Unhandled exceptions in `POST /chat/ask` return a generic `"Internal server error"`, logging stack traces strictly to server logs.
- **Client IP Tracking**: Nginx only trusts `CF-Connecting-IP` originating from the trusted Docker subnet `172.28.0.0/16`.
- **Identity & Access**: MOD-SA is an open student advisory assistant; no student authentication is currently required. If documents containing private student records or confidential data are added in the future, OAuth2 / SSO integration should be placed in front of Nginx.
