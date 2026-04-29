#!/bin/bash
# AxionX Demo Environment — Replit Deployment Startup Script
#
# Use this as the deployment run command in a FORKED Replit configured for demo.
# In .replit [deployment] section of the demo fork, set:
#
#   run = ["bash", "startup_demo_replit.sh"]
#
# Required Replit Secrets (set in the forked Replit's Secrets panel):
#   AXIONX_DEMO_MODE       = true
#   AXIONX_DB_PATH         = ./axion_demo.db
#   SECRET_KEY             = <random 64-char hex>
#
# Optional Secrets:
#   AXIONX_DEMO_RESET_CRON = 03:00   # default — nightly reset at 3 AM AEST
#                            disabled # to turn off scheduled resets
#
# All other vars (SMTP, Azure, APNs) can be omitted — comms are intercepted.

set -e

# ─── Demo environment variables ──────────────────────────────────────────────
export AXIONX_DEMO_MODE=true
export AXIONX_DB_PATH="${AXIONX_DB_PATH:-./axion_demo.db}"
export AXIONX_DEMO_DB_PATH="$AXIONX_DB_PATH"

# Ensure DB directory exists (handles paths like ./data/axion_demo.db)
DEMO_DB_DIR="$(dirname "$AXIONX_DB_PATH")"
mkdir -p "$DEMO_DB_DIR"

# ─── Startup banner ───────────────────────────────────────────────────────────
echo "================================================================"
echo "AxionX DEMO MODE ACTIVE — NO LIVE DATA"
echo "DB_PATH : $AXIONX_DB_PATH"
echo "================================================================"

# ─── Auto-seed demo DB if absent ─────────────────────────────────────────────
if [ ! -f "$AXIONX_DB_PATH" ]; then
    echo "[demo-startup] Demo DB not found — seeding now..."
    python3 scripts/seed_demo.py
    if [ $? -ne 0 ]; then
        echo "[demo-startup] ERROR: seed_demo.py failed. Aborting startup."
        exit 1
    fi
    echo "[demo-startup] Demo DB seeded successfully."
else
    echo "[demo-startup] Demo DB found — skipping seed."
fi

# ─── Start demo scheduler in background ──────────────────────────────────────
# demo_scheduler.py exits immediately if AXIONX_DEMO_MODE is not set,
# so it is safe to unconditionally launch it here.
echo "[demo-startup] Starting demo auto-reset scheduler..."
python3 demo_scheduler.py &
SCHED_PID=$!
echo "[demo-startup] Demo scheduler started (PID $SCHED_PID, cron=${AXIONX_DEMO_RESET_CRON:-03:00} AEST)"

# ─── Launch gunicorn ─────────────────────────────────────────────────────────
# Replit deployments use port 5000 by default.
exec gunicorn \
    --bind "0.0.0.0:${PORT:-5000}" \
    --timeout 120 \
    --workers 2 \
    --capture-output \
    --log-level warning \
    wsgi:application
