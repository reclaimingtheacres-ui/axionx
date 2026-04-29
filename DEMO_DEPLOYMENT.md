# AxionX Demo Deployment Guide

This guide explains how to create a publicly accessible demo of AxionX using a separate
Replit deployment. The demo runs fully isolated from production — it uses its own database,
intercepts all outbound communications, and stamps every generated document as
"DEMO DOCUMENT — NOT FOR OPERATIONAL USE".

---

## What the demo includes

| What | Detail |
|------|--------|
| Separate database | `axion_demo.db` — never touches `axion.db` |
| Auto-seed on first boot | `scripts/seed_demo.py --reset` runs automatically if the DB is absent |
| Intercepted comms | All email, SMS, and push notifications go to `/demo/outbox` — nothing is sent |
| Watermarked documents | Form 13, VIR, Transport Instructions all stamped DEMO |
| One-click role login | `/demo` — choose Admin, Field Agent, or Client/Lender persona |
| Admin reset | `/demo` → "Reset Demo Data" button wipes and re-seeds without touching production |
| Health endpoint | `/demo/health` returns JSON — useful for uptime monitors |

---

## Setup: Fork and configure

### Step 1 — Fork this Replit

1. Open this Replit project in your browser.
2. Click the three-dot menu → **Fork**.
3. Name the fork something like **AxionX Demo**.
4. The fork gets its own isolated environment — it will never affect the original.

### Step 2 — Set Secrets in the fork

In the forked Replit, open **Secrets** (padlock icon in the sidebar) and add:

| Secret name | Value |
|-------------|-------|
| `AXIONX_DEMO_MODE` | `true` |
| `AXIONX_DB_PATH` | `./axion_demo.db` |
| `SECRET_KEY` | A random 64-character hex string (run `python3 -c "import secrets; print(secrets.token_hex(32))"`) |

> **Do not set** SMTP credentials, Azure Blob, or APNs keys — the app intercepts all
> outbound comms in demo mode so these are not needed and not used.

### Step 3 — Apply the demo Replit configuration

The repo includes a ready-to-use configuration template at `.replit.demo`. In the
forked Replit, **replace the entire contents of `.replit`** with the content from
`.replit.demo` (everything between the `BEGIN` and `END` markers).

This sets the deployment run command to `bash startup_demo_replit.sh`, which will:
- Export `AXIONX_DEMO_MODE=true`
- Seed `axion_demo.db` automatically if it does not exist
- Start gunicorn on port 5000

### Step 4 — Publish

1. Click **Publish** (or **Deploy**) in the Replit header.
2. Choose **Autoscale** (recommended — cost-effective for demo traffic).
3. The deployed URL will be something like `https://axionx-demo.your-username.replit.app`.
4. Share the URL — visitors land on `/demo` automatically.

---

## Entry point

The demo landing page is at `/demo`. Visitors choose a role:

- **Admin** — full platform access, can reset demo data
- **Field Agent** — mobile-first field operations view
- **Client / Lender** — filtered view of one client's portfolio

No password is required for any demo role.

---

## Resetting demo data

While signed in as the Admin demo persona, visit `/demo` — an **Admin Controls** card
appears at the bottom of the page. Click **Reset Demo Data**, type the confirmation phrase,
and the database is wiped and re-seeded in the background (usually takes 5–15 seconds).
You are signed out automatically when the reset completes.

Alternatively, trigger a reset via the deployment startup by deleting `axion_demo.db` and
restarting the deployment — the startup script will re-seed automatically.

---

## Environment variable reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AXIONX_DEMO_MODE` | Yes | — | `true` activates demo mode |
| `AXIONX_DB_PATH` | Yes | `./axion_demo.db` | Path to the demo SQLite database |
| `AXIONX_DEMO_DB_PATH` | No | same as `AXIONX_DB_PATH` | Alias — either name works |
| `SECRET_KEY` | Yes | — | Flask session signing key |

All other vars (SMTP, Azure, APNs, OpenAI) are optional in demo mode — external calls
are either intercepted or skipped.

---

## Keeping demo and production separate

The safety model has three layers:

1. **Hard startup fail** — If `AXIONX_DEMO_MODE=true` but `AXIONX_DB_PATH` resolves to
   `axion.db`, the app refuses to start.
2. **Write guard** — All DB write operations check that the active path is not the
   production default before executing.
3. **Separate Replit fork** — The demo lives in a completely separate environment. The
   production Replit's `axion.db` is never mounted or accessible in the fork.

---

## Relevant files

| File | Purpose |
|------|---------|
| `.replit.demo` | Drop-in `.replit` config for the demo fork — copy its content into the fork's `.replit` |
| `startup_demo_replit.sh` | Startup script for Replit demo deployment |
| `startup_demo.sh` | Startup script for Azure App Service demo deployment |
| `.env.example` | Documents all required env vars including demo-specific vars |
| `scripts/seed_demo.py` | Seeds the demo database with realistic fake data |
| `scripts/demo_schema.sql` | Schema used by the seed script |
| `app.py` lines 116–155 | Demo mode init, safety guard, startup banner |
| `templates/demo_landing.html` | `/demo` entry page with role selection and reset button |
| `templates/demo_reset.html` | Reset confirmation page (also accessible directly) |
