#!/usr/bin/env bash
# Entrypoint for the inmo-webhook container.
#
# 1. Applies pending database migrations; the first migration creates the
#    properties, leads, and neighborhoods tables (with triggers and seed data).
# 2. Starts the FastAPI application with uvicorn.
#
# DATABASE_URL is required: main.py raises a ValueError at startup if it is
# empty (the file-log store is retired and Postgres is mandatory), so a missing
# DATABASE_URL here is a misconfiguration, not an optional path. Migrations are
# only skipped when DATABASE_URL is unset on an env where it is not needed.
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] DATABASE_URL not set — skipping database migrations."
else
  echo "[entrypoint] Applying database migrations..."
  alembic upgrade head
fi

echo "[entrypoint] Starting uvicorn on 0.0.0.0:8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
