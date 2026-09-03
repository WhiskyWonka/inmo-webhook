#!/usr/bin/env bash
# Entrypoint for the inmo-webhook container.
#
# 1. Applies pending database migrations; the first migration creates the
#    properties, leads, and neighborhoods tables (with triggers and seed data).
# 2. Starts the FastAPI application with uvicorn.
#
# If DATABASE_URL is not set, migrations are skipped and the server still
# starts so the webhook can run without a database (e.g. local development).
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] DATABASE_URL not set — skipping database migrations."
else
  echo "[entrypoint] Applying database migrations..."
  alembic upgrade head
fi

echo "[entrypoint] Starting uvicorn on 0.0.0.0:8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
