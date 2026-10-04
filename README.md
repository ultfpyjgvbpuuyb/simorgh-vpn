# Simorgh (سیمرغ)

A lightweight self-hosted panel for managing Xray (VLESS + Reality) users: quota and expiry limits,
per-user subscription links, and a branded Persian subscription page.

- **Backend:** FastAPI + SQLite (single container, Xray runs as a managed subprocess)
- **Admin dashboard:** `/admin`
- **Subscription link:** `/sub/<token>` → the app config for VPN clients, a branded page for browsers
  (add `?raw=1` to force the raw config)

## Quick start

```bash
git clone <your-repo> simorgh && cd simorgh
cp .env.example .env
```

1. Generate Reality keys: `docker run --rm $(docker build -q .) xray x25519`
   Put them in `REALITY_PRIVATE_KEY` / `REALITY_PUBLIC_KEY`, and `openssl rand -hex 8` in `REALITY_SHORT_ID`.
2. Set `ADMIN_PASS`, `PANEL_SECRET`, `SERVER_HOST`, `PUBLIC_BASE_URL`.
3. `docker compose up -d --build`
4. Open `http://SERVER_IP:8000/admin` and create your first user.

## Security checklist (read before going public)

- Xray uses port 443, so serve the panel over HTTPS on **another** port with a reverse proxy
  (e.g. Caddy: `panel.example.com:8443 { reverse_proxy localhost:8000 }`) and set `PUBLIC_BASE_URL` to that URL.
  Without HTTPS, the admin password and subscription tokens travel in clear text.
- Firewall port 8000 so only the reverse proxy reaches it.
- Xray's stats API listens on `127.0.0.1:10085` only. Don't expose it.
- Use a long `ADMIN_PASS`. Tokens in sub links are random and unguessable; rotate by deleting and recreating the user.

## How it works

- Every 30 s the panel reads per-user traffic from Xray's stats API, updates usage, and disables users
  who are over quota or expired. Xray is restarted only when the set of active users changes
  (this briefly drops connections).
- Users with quota 0 are not supported; always set a limit.

## Limitations / ideas

Single inbound, single server, one admin, no per-IP device limits. Natural next steps: multiple admins,
node support, Telegram bot, device limits, traffic charts in the dashboard.
