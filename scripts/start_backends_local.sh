#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Installing backend dependencies..."
python -m pip install -r backend/requirements.txt

echo "[2/3] Running Django migrations..."
python backend/django_app/manage.py migrate

echo "[3/3] Starting Django and FastAPI..."
python backend/django_app/manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!

cleanup() {
  echo "Stopping Django (PID: ${DJANGO_PID})..."
  kill "${DJANGO_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uvicorn --app-dir backend/fastapi_ai main:app --host 0.0.0.0 --port 8001 --reload
