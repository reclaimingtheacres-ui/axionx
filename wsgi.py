"""
WSGI entry point for Azure App Service / any WSGI host.

Exposes 'application' so the server can be started as:
    gunicorn wsgi:application

Both app:app and wsgi:application are valid.
app:app is preferred for clarity.
"""
import os
import sys

# Ensure the directory containing this file is on sys.path.
# This makes the module importable regardless of gunicorn's working directory.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from app import app  # noqa: E402

application = app
