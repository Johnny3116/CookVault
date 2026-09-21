#!/bin/sh
# Migrations run on every boot so a fresh clone (or a schema change) doesn't
# need a remembered manual step. `alembic upgrade head` is a no-op when the
# database is already current.
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting CookVault API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
