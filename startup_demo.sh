#!/bin/bash
# AxionX Demo Environment Startup Script
# Deployed to: Azure App Service  axionx-demo  (demo.axionx.com.au)
#
# This script is used as the Azure App Service startup command via Oryx.
# Set it in the Azure portal: Configuration → General settings → Startup command
#   startup_demo.sh
# OR via az CLI:
#   az webapp config set --name axionx-demo --resource-group <rg> --startup-file startup_demo.sh
#
# Required App Service environment variables (set via Azure portal or az CLI):
#   AXIONX_DEMO_MODE=true
#   AXIONX_DB_PATH=/home/site/data/axion_demo.db
#   SECRET_KEY=<random-64-char-hex>
#
# Optional:
#   AXIONX_DEMO_RESET_CRON=03:00   # nightly auto-reset time (AEST). Set to "disabled" to turn off.
#   (All other SMTP/Azure vars can be omitted — comms are intercepted in demo mode)

set -e

# ─── Demo environment variables ──────────────────────────────────────────────
export AXIONX_DEMO_MODE=true
export AXIONX_DB_PATH="${AXIONX_DB_PATH:-/home/site/data/axion_demo.db}"
export AXIONX_DEMO_DB_PATH="$AXIONX_DB_PATH"

# Persistent storage directory — /home/site/data survives restarts on Azure
DEMO_DB_DIR="$(dirname "$AXIONX_DB_PATH")"
mkdir -p "$DEMO_DB_DIR"

# ─── Startup banner ───────────────────────────────────────────────────────────
echo "================================================================"
echo "AxionX DEMO MODE ACTIVE — NO LIVE DATA"
echo "DB_PATH : $AXIONX_DB_PATH"
echo "HOST    : ${WEBSITE_HOSTNAME:-localhost}"
echo "================================================================"

# ─── Auto-seed demo DB if absent ─────────────────────────────────────────────
if [ ! -f "$AXIONX_DB_PATH" ]; then
    echo "[demo-startup] Demo DB not found at $AXIONX_DB_PATH — seeding now..."
    python3 scripts/seed_demo.py
    if [ $? -ne 0 ]; then
        echo "[demo-startup] ERROR: seed_demo.py failed. Aborting startup."
        exit 1
    fi
    echo "[demo-startup] Demo DB seeded successfully."
else
    echo "[demo-startup] Demo DB found at $AXIONX_DB_PATH — skipping seed."
fi

# ─── Start demo scheduler in background ──────────────────────────────────────
# demo_scheduler.py exits immediately if AXIONX_DEMO_MODE is not set,
# so it is safe to unconditionally launch it here.
echo "[demo-startup] Starting demo auto-reset scheduler..."
python3 demo_scheduler.py &
SCHED_PID=$!
echo "[demo-startup] Demo scheduler started (PID $SCHED_PID, cron=${AXIONX_DEMO_RESET_CRON:-03:00} AEST)"

# ─── Launch gunicorn ─────────────────────────────────────────────────────────
exec gunicorn \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --workers 2 \
    --capture-output \
    --log-level warning \
    wsgi:application
