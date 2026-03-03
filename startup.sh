#!/usr/bin/env bash
set -e

# Azure deployments sometimes place code in /home/site/wwwroot/repository
if [ -d "/home/site/wwwroot/repository" ]; then
  cd /home/site/wwwroot/repository
else
  cd /home/site/wwwroot
fi

exec gunicorn --bind 0.0.0.0:${PORT:-8000} --timeout 600 app:app
