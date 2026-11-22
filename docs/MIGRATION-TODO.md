# Migration and cleanup checklist: Vercel/ngrok to on-prem Nginx

Goal: finish moving the frontend from Vercel to `https://modsa.project.cpe.kmutt.ac.th/`
(one Nginx serves the React build and proxies `/api/*`) and remove the leftovers.
Do these in order. Nothing here has been run unless marked **done**.

## Status

- **done** Frontend served by Nginx (`nginx/Dockerfile`, `nginx/nginx.conf`).
- **done** Verified on the VM on `127.0.0.1:8080`: `/`, assets, SPA fallback, JSON 404s,
  413, rate limit, real chat answer with sources, built JS uses `/api`.
- **done** Prod override `docker-compose.prod.yml` (port 80) and `limit_req_status 429`
  pushed to `dev` as `7e6792c`.
- **done** Browser check passed on the deployed VM.
- **not done** Merge to `main`, retire Vercel, cleanup, real-IP and TLS items below.

## 1. Merge to main

- [ ] Open a PR `dev` -> `main` on GitHub; confirm it contains `7e6792c`.
- [ ] Merge it yourself (do not force-push, do not delete `archive/*` tags).
- [ ] On the VM:
  ```bash
  cd ~/modsa-deployment
  git checkout main && git pull
  sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  sudo docker ps --format '{{.Names}}\t{{.Ports}}\t{{.Status}}'
  curl -i http://127.0.0.1/api/health
  ```
- [ ] Always start production with the prod override. The local override binds only
  `127.0.0.1:8080` and drops port 80.
- [ ] Rollback: `git checkout --detach b81f916`, then
  `sudo docker compose -f docker-compose.yml -f docker-compose.local.yml --profile tunnel up -d --build`.

## 2. Client IP and rate limits (most important open risk)

- [ ] TODO(owner): find how traffic reaches Nginx (published port, reverse proxy, load
  balancer) and where TLS terminates. The repo does not say.
- [ ] From another device, load the site, then run
  `sudo docker compose logs nginx --tail 20`. If the first field is always the same
  internal address, every user shares one rate-limit bucket (30 requests/min per IP,
  burst 10).
- [ ] Set `set_real_ip_from` in `nginx/nginx.conf` to the real front proxy address.
  It currently trusts `172.28.0.0/16` only. Do not guess the value.
- [ ] Spoof test from outside:
  `curl -s -o /dev/null https://modsa.project.cpe.kmutt.ac.th/api/health -H 'X-Forwarded-For: 1.2.3.4'`
  then check the log: the first field must be the caller's real IP, not `1.2.3.4`.
- [ ] Rate-limited requests should now return 429 (not 503). Check against the VM only,
  never against the public host.

## 3. Retire Vercel

- [ ] Keep the Vercel project for about a week as a fallback.
- [ ] Tell users about the new URL, or redirect the old one if people use it.
- [ ] Remove the Vercel env vars (`VITE_API_URL`, `VITE_NGROK_SKIP_BROWSER_WARNING`), then
  delete the Vercel project.
- [ ] Remove the Vercel origin from `CORS_ORIGINS` in the VM `.env`. Same-origin needs no
  CORS. Apply with `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
  (`restart` does not re-read `.env`).

## 4. Retire ngrok

- [ ] Confirm nothing still uses the ngrok URL.
- [ ] Delete the ngrok static domain / authtoken in the ngrok dashboard (rotate the token if
  it was ever shared).
- [ ] Remove `NGROK_AUTHTOKEN` and `NGROK_DOMAIN` from the VM `.env`.
- [ ] Remove the `ngrok` service from `docker-compose.yml`, the ngrok lines in
  `.env.vm.example`, and the "Legacy fallback" section 10 in `DEPLOYMENT.md`.
- [ ] Remove the `NGROK_*` rows from the README config table.

## 5. Repo cleanup

- [ ] `docs/DEPLOYMENT.md`: still describes Vercel and ngrok. Delete it, or reduce it to a
  one-line pointer to the root `DEPLOYMENT.md`. Update the README link if needed.
- [ ] Delete `docs/NGROK_VERCEL_IMPLEMENTATION_REPORT.md` and `docs/NGROK_VERCEL_STATUS.md`.
- [ ] Review `docs/deployment-plan-free-tier.md` for stale Vercel/ngrok/Render content.
- [ ] `render.yml`: delete if Render is no longer a fallback.
- [ ] Remove the `modsa-vm` branch only if the owner agrees. Never delete `archive/*` tags.
- [ ] Update the README and `DEPLOYMENT.md` so the production start command is the prod
  override, and remove the "legacy fallback" wording.
- [ ] On the machine with the WIP stash: review `stash@{0}`
  ("wip-before-onprem-nginx-task 2026-11-23"), then drop it only once you are sure nothing
  in it is needed. It conflicts with the committed setup (removes the real-IP lines and
  ngrok service, adds `ports: 80:80`, rewrites the docs).

## 6. Backend follow-ups

- [ ] A real chat took 37 s on the VM; the frontend aborts at 45 s. Check `LLM_TIMEOUT`,
  model choice and the thinking setting in `.env` (see `DEPLOYMENT.md` section 7 and 8).
- [ ] Pin dependency versions in `backend/requirements.txt`.

## 7. Later: KMUTT OAuth2 login

- [ ] Not implemented. Needs an approved design first (callback URL on
  `modsa.project.cpe.kmutt.ac.th`, session or token handling, which routes need login).
