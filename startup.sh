#!/usr/bin/env bash
set -e

# ── Determine deployment root ────────────────────────────────────────────────
# Azure Oryx sometimes places source under wwwroot/repository when using
# GitHub Actions deployment; plain zip/git deploy lands in wwwroot directly.
if [ -d "/home/site/wwwroot/repository" ]; then
    APP_ROOT="/home/site/wwwroot/repository"
else
    APP_ROOT="/home/site/wwwroot"
fi

echo "[startup] APP_ROOT=$APP_ROOT"

# ── Activate Oryx virtual environment ────────────────────────────────────────
# Oryx creates 'antenv' inside the app root after installing requirements.txt
ANTENV="$APP_ROOT/antenv/bin/activate"
if [ -f "$ANTENV" ]; then
    echo "[startup] activating $ANTENV"
    # shellcheck disable=SC1090
    source "$ANTENV"
else
    echo "[startup] antenv not found, using system Python"
fi

# ── Ensure the app directory is on the Python module search path ─────────────
# This is the critical fix: gunicorn must be able to import 'app' and Azure
# does not guarantee cwd == APP_ROOT when launching the startup command.
export PYTHONPATH="$APP_ROOT${PYTHONPATH:+:$PYTHONPATH}"
echo "[startup] PYTHONPATH=$PYTHONPATH"

# ── Launch ────────────────────────────────────────────────────────────────────
exec gunicorn \
    --chdir "$APP_ROOT" \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 600 \
    --workers 2 \
    --access-logfile - \
    --error-logfile - \
    app:app
