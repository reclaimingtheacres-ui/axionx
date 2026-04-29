#!/bin/bash
set -e

echo "[post-merge] Starting post-merge setup..."

echo "[post-merge] Installing Python dependencies..."
pip install -r requirements.txt -q

echo "[post-merge] Done."
