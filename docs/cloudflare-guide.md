# Cloudflare Tunnel guide — expose local bge-m3 to Render

Windows dev machine. Assumes you have a domain added to Cloudflare (free plan works — just need a domain, e.g. from Namecheap/Cloudflare registrar, with nameservers pointed at Cloudflare).

## 1. Run bge-m3 locally

Ollama:
```bash
ollama pull bge-m3
ollama serve
```
Defaults to `http://127.0.0.1:11434`. Confirm:
```bash
curl http://127.0.0.1:11434/api/tags
```

## 2. Install cloudflared (Windows)

```powershell
winget install --id Cloudflare.cloudflared
```
Verify:
```powershell
cloudflared --version
```

## 3. Login and create named tunnel

```powershell
cloudflared tunnel login
```
Opens browser, pick the domain you added to Cloudflare. Then:
```powershell
cloudflared tunnel create modsa-embeddings
```
Outputs a tunnel ID and writes credentials to `%USERPROFILE%\.cloudflared\<tunnel-id>.json`. Note the ID.

## 4. Route a hostname to the tunnel

```powershell
cloudflared tunnel route dns modsa-embeddings embeddings.yourdomain.com
```
Creates the CNAME in Cloudflare DNS automatically.

## 5. Config file

Create `%USERPROFILE%\.cloudflared\config.yml`:
```yaml
tunnel: modsa-embeddings
credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: embeddings.yourdomain.com
    service: http://127.0.0.1:11434
  - service: http_status:404
```
Replace `<you>` and `<tunnel-id>` with real values. Last rule (`http_status:404`) is required as catch-all.

## 6. Test it manually first

```powershell
cloudflared tunnel run modsa-embeddings
```
Keep it running, then in another terminal/browser hit `https://embeddings.yourdomain.com/api/tags` — should return same as local curl. Ctrl+C to stop once confirmed.

## 7. Install as Windows service (auto-start, auto-restart)

```powershell
cloudflared service install
```
Registers it as a Windows service using your `config.yml`. Runs on boot, restarts on crash by default (Windows service recovery).

Start/check it:
```powershell
Start-Service cloudflared
Get-Service cloudflared
```

To view logs, check Windows Event Viewer under Application logs, source `cloudflared`, or run manually with `cloudflared tunnel run modsa-embeddings` for live output when debugging.

If `cloudflared service install` gives trouble, fallback: Task Scheduler task, trigger "At startup", action `cloudflared.exe tunnel run modsa-embeddings`, "Run whether user is logged in or not", enable "Restart on failure".

## 8. Point Render at it

In Render dashboard → your backend service → Environment:
```
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=https://embeddings.yourdomain.com
EMBEDDING_MODEL=bge-m3
```
Redeploy (or it picks up on next deploy/restart).

## 9. Verify end to end

```bash
curl -X POST https://your-render-app.onrender.com/admin/reindex -H "X-Admin-Key: <your key>"
curl -X POST https://your-render-app.onrender.com/chat/ask -H "Content-Type: application/json" -d '{"question":"..."}'
```
Should return real answer with sources — confirms Render reached your home PC's embedding server through the tunnel.

## Keep in mind

- PC must stay on, Ollama running, tunnel service running — whenever Render needs to embed/query. Sleep/hibernate or Wi-Fi drop breaks it.
- Named tunnel URL stays fixed across restarts — no need to update Render env again once set.
- Rotate/revoke: `cloudflared tunnel delete modsa-embeddings` removes it if you stop using this approach.
