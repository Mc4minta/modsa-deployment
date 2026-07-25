# Host bge-m3 locally with Ollama + expose via Cloudflare Tunnel (free)

Intensive step-by-step. Windows dev machine. Goal: Render's backend calls your home PC for embeddings, free of charge.

## Honesty check on "free"

- Ollama: free.
- Cloudflare Tunnel service: free, no rate limit.
- **Fixed hostname needs a domain you own in Cloudflare.** Domain registration itself is usually **not** free (~$8-15/yr from most registrars, Cloudflare Registrar included). If you already own any domain, use a subdomain of it — zero extra cost. If you own none:
  - Cheapest real option: buy one cheap domain (e.g. `.xyz`, `.click` often <$2 first year) — pay once.
  - Free-but-unstable fallback: skip named tunnel, use a **quick tunnel** (`cloudflared tunnel --url http://localhost:11434`, no login, no domain). Gives a random `*.trycloudflare.com` URL that changes every time you restart it — means updating `EMBEDDING_BASE_URL` on Render each time. Fine only for short demos, not for "set once and forget."

This guide covers both paths — pick based on whether you have a domain.

---

## Part A — Run bge-m3 locally with Ollama

### A1. Install Ollama

Download and install from [ollama.com/download](https://ollama.com/download) (Windows installer). Free.

### A2. Pull the bge-m3 model

```powershell
ollama pull bge-m3
```

### A3. Start Ollama serving

Ollama runs as a background service after install (check system tray icon). If not running:
```powershell
ollama serve
```
Default bind: `http://127.0.0.1:11434`.

### A4. Confirm it works locally

```powershell
curl http://127.0.0.1:11434/api/tags
```
Should list `bge-m3` in the JSON response.

Test an actual embedding call:
```powershell
curl http://127.0.0.1:11434/api/embeddings -d '{\"model\":\"bge-m3\",\"prompt\":\"test\"}'
```
Should return a vector (`embedding: [...]`).

---

## Part B — Install cloudflared

```powershell
winget install --id Cloudflare.cloudflared
cloudflared --version
```

---

## Part C — Path 1: you own a domain (stable, recommended)

### C1. Add your domain to Cloudflare (if not already)

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Add a site** → enter your domain.
2. Pick the **Free** plan.
3. Cloudflare gives you two nameservers — go to your registrar (wherever you bought the domain) and update nameservers to Cloudflare's. Takes minutes to a few hours to propagate.
4. Wait until Cloudflare dashboard shows the site as **Active**.

### C2. Login cloudflared to your Cloudflare account

```powershell
cloudflared tunnel login
```
Opens browser — select your domain, authorize.

### C3. Create a named tunnel

```powershell
cloudflared tunnel create modsa-embeddings
```
Note the tunnel ID printed, and the credentials file path (`%USERPROFILE%\.cloudflared\<tunnel-id>.json`).

### C4. Route a hostname to the tunnel

```powershell
cloudflared tunnel route dns modsa-embeddings embeddings.yourdomain.com
```
Auto-creates the CNAME DNS record in Cloudflare.

### C5. Write the config file

Create `%USERPROFILE%\.cloudflared\config.yml`:
```yaml
tunnel: modsa-embeddings
credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: embeddings.yourdomain.com
    service: http://127.0.0.1:11434
  - service: http_status:404
```
Replace `<you>` and `<tunnel-id>` with your actual values.

### C6. Test manually

```powershell
cloudflared tunnel run modsa-embeddings
```
In another window:
```powershell
curl https://embeddings.yourdomain.com/api/tags
```
Should match the local response from A4. Ctrl+C to stop once confirmed.

### C7. Install as an auto-restarting Windows service

```powershell
cloudflared service install
Start-Service cloudflared
Get-Service cloudflared
```
Now it starts on boot and Windows service recovery restarts it on crash.

If `service install` fails, fallback via Task Scheduler:
- New Task → Trigger: **At startup**.
- Action: `cloudflared.exe tunnel run modsa-embeddings`.
- Check **Run whether user is logged in or not**.
- On the **Settings** tab, enable restart-on-failure options.

### C8. Set Render env vars

Render dashboard → your backend service → Environment:
```
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=https://embeddings.yourdomain.com
EMBEDDING_MODEL=bge-m3
```
Remove/leave commented any `huggingface` embedding vars from before. Save — Render redeploys.

### C9. Verify end to end

```bash
curl -X POST https://<your-render-service>.onrender.com/admin/reindex -H "X-Admin-Key: <ADMIN_API_KEY>"
curl -X POST https://<your-render-service>.onrender.com/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
```
Grounded answer with sources confirms Render reached your home PC through the tunnel.

---

## Part C — Path 2: no domain, quick tunnel (free, unstable URL)

Use only for short testing sessions, not unattended production.

### C2'. Run a quick tunnel

```powershell
cloudflared tunnel --url http://localhost:11434
```
Terminal prints a random URL like `https://random-words-1234.trycloudflare.com`. No login needed.

### C3'. Set Render env vars with that URL

```
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=https://random-words-1234.trycloudflare.com
EMBEDDING_MODEL=bge-m3
```
Save, wait for Render redeploy.

### C4'. Caveats

- Closing the terminal or restarting the tunnel gives a **new URL** — you must update `EMBEDDING_BASE_URL` on Render again each time.
- No auto-restart story here; if this terminal closes, embeddings stop working until you relaunch and update Render.
- Fine for a live demo you're personally driving; not fine for "leave it running overnight for grading."

---

## Keeping it running

Whichever path: Ollama must be running, bge-m3 loaded, cloudflared tunnel (named or quick) must be active, PC powered on and networked — every time Render needs to answer a question. If any of those stop, `/chat/ask` on the live site will fail or time out on embedding calls.

## Cleanup / rollback

```powershell
cloudflared service uninstall
cloudflared tunnel delete modsa-embeddings
```
Then switch Render's `EMBEDDING_PROVIDER` back to `huggingface` (§4/§4b in [deployment-plan-free-tier.md](deployment-plan-free-tier.md)) if you stop self-hosting.
