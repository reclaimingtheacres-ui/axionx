#!/usr/bin/env bash
set -e

# Azure Oryx extracts the app to a temp path and sets CWD to that location.
# Use $PWD as the authoritative app root — do not hardcode /home/site/wwwroot.
APP_ROOT="$(pwd)"
echo "[startup] APP_ROOT=$APP_ROOT"

# Activate the Oryx-built virtual environment if present (named 'antenv').
ANTENV="$APP_ROOT/antenv/bin/activate"
if [ -f "$ANTENV" ]; then
    echo "[startup] activating $ANTENV"
    # shellcheck disable=SC1090
    source "$ANTENV"
else
    echo "[startup] antenv not found, using system Python"
fi

# Put the app root on PYTHONPATH so gunicorn can import app/wsgi regardless
# of how it resolves its own working directory internally.
export PYTHONPATH="$APP_ROOT${PYTHONPATH:+:$PYTHONPATH}"
echo "[startup] PYTHONPATH=$PYTHONPATH"

# The persistent SQLite database lives on Azure's mounted storage, not in the
# extracted /tmp deployment artifact.  Set DB_PATH so both app.py and
# geoop_import.py resolve to the same persistent file.
export DB_PATH="${DB_PATH:-/home/site/data/axion.db}"
echo "[startup] DB_PATH=$DB_PATH"

# Ensure the data directory exists (first deploy).
mkdir -p "$(dirname "$DB_PATH")"

exec gunicorn \
    --chdir "$APP_ROOT" \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 600 \
    --workers 1 \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
