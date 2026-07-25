# Research: exposing local bge-m3 embedding server to Render via tunnel

Date: 2026-07-26

## Goal

Run bge-m3 (embedding model) locally on your own device (via Ollama or text-embeddings-inference), expose it as a public HTTPS endpoint, point `EMBEDDING_BASE_URL` in Render's backend at it — instead of paying for a hosted embedding API.

## Tunnel options compared

### Cloudflare Tunnel (recommended)

- Free, no rate limits, no time-boxed URLs.
- Named tunnel gives a **fixed URL** tied to your own domain/subdomain — stops and restarts (even days later) keep working at the same URL. Ephemeral "quick tunnels" (no login) get a random URL each run — avoid these for this use case.
- Outbound-only connection from your PC to Cloudflare edge — no port forwarding, no exposed public IP, no firewall changes.
- Runs as a systemd service (Linux) or Windows service — `Restart=on-failure` config makes it auto-reconnect after crash/network blip, and can auto-start on boot.
- Uses QUIC (HTTP/3) by default as of 2026 — faster reconnect, more resilient on flaky home internet than older versions.
- Setup: `cloudflared tunnel login` → `cloudflared tunnel create <name>` → map hostname → run as service pointing at `http://localhost:<port>` (your bge-m3 server port).

### ngrok

- Free tier: random subdomain that **rotates every restart** — bad fit for a Render config that expects a stable `EMBEDDING_BASE_URL`. Fixing that requires a paid plan (custom/reserved domain).
- Better live traffic inspection/debugging UI — useful during initial setup, not needed for steady-state production use.
- No systemd-native persistence story as clean as cloudflared; typically wrapped in your own supervisor script.

### Verdict

Cloudflare Tunnel fits this case better: free, stable URL via named tunnel, native auto-restart via systemd, no rate limits on request volume (matters since embeddings get called per chat message).

## Remaining real risk (applies to any tunnel choice)

Tunneling only solves the network path. It does NOT solve:
- **Uptime**: if your PC sleeps, loses power, or the home ISP drops, Render's backend loses its embedding provider — chat breaks live in production.
- **Latency**: round trip to your home network adds delay vs a datacenter-hosted API.
- **No official SLA** — fine for a demo/thesis project, risky if this needs to stay up unattended for judges/users.

## Recommended setup if you proceed with Cloudflare Tunnel

1. Run bge-m3 locally (Ollama `ollama pull bge-m3` or HF text-embeddings-inference container) bound to `127.0.0.1:<port>`.
2. Install `cloudflared`, run `cloudflared tunnel login`, create a named tunnel, map a hostname (e.g. `embeddings.yourdomain.com`) to `http://localhost:<port>`.
3. Install as a system service with auto-restart (systemd on Linux, or Windows Task Scheduler / NSSM on Windows since your dev machine is Windows) so it survives reboots.
4. Set `EMBEDDING_BASE_URL=https://embeddings.yourdomain.com` and `EMBEDDING_PROVIDER=ollama` (or whatever provider matches your local server's API shape) in Render's env vars.
5. Keep your PC powered on and networked whenever the deployed app needs to serve real traffic.

## Alternative if uptime is a concern

Your `config.py` already supports `EMBEDDING_PROVIDER=huggingface` — HF Inference API can serve bge-m3 directly, no local hosting or tunnel needed, and removes the home-PC-uptime dependency entirely. Worth using for anything beyond local dev/demo where you control exactly when it's being tested.

## Sources

- [Cloudflare Tunnel in 2026: Expose localhost Without Opening Ports or Buying an IP](https://recca0120.github.io/en/2026/04/14/cloudflare-tunnel-2026/)
- [Cloudflare Tunnel: Ngrok Alternative for Serving Local APIs](https://aslan.md/cloudflare-tunnel-ngrok-alternative-for-serving-local-apis/)
- [Step-by-Step Guide: Setting Up Persistent Cloudflare Tunnels for Multiple Local Ports](https://techify.blog/blog/setting-up-persistent-cloudflare-tunnels-for-multiple-ports)
- [Tunnel run parameters · Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)
- [Skip the Cloud Bill: Connect Your Dev Backend to Cloudflare Tunnel](https://cavecafe.medium.com/build-a-free-dev-backend-with-cloudflare-tunnel-f66e3870f75e)
