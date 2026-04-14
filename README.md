# Glunova

AI-powered healthcare platform focused on diabetes monitoring, prevention, and care coordination.

## Architecture

- `frontend/`: Next.js user interface.
- `backend/django_app`: core API for authentication, RBAC, and clinical data management.
- `backend/fastapi_ai`: AI engine for screening, psychology, nutrition, clinic, and kids services.
- Shared PostgreSQL on Supabase via `DATABASE_URL`.

## Prerequisites

- Python 3.11+
- Node.js 20+
- pnpm
- Docker Desktop (optional, for containerized backend)
- GNU Make (optional, for shortcut commands)

## Environment Setup

Create `backend/.env` (or copy from `backend/.env.example`) and set:

- `DATABASE_URL` (Supabase PostgreSQL URL with `sslmode=require`)
- `DJANGO_SECRET_KEY`
- `JWT_SHARED_SECRET`
- `DJANGO_DEBUG` (usually `true` for dev)

## Run Backend (Docker)

Quick start with Makefile:

```bash
make backend-rebuild
```

Useful commands:

```bash
make backend-up
make backend-logs
make backend-down
```

From repository root:

```bash
docker compose up --build
```

Backend URLs:

- Django API: `http://localhost:8000`
- FastAPI API: `http://localhost:8001`
- FastAPI docs: `http://localhost:8001/docs`

## Run Backend (Local)

Install dependencies once:

```bash
pip install -r backend/requirements.txt
```

Run both backends with one command:

```bash
make backend-local
```

On Linux/macOS (or Git Bash), use:

```bash
make backend-local-unix
```

Or use the script directly:

```bash
bash scripts/start_backends_local.sh
```

Windows script:

```bat
scripts\start_backends_local.bat
```

Manual alternative:

Run Django:

```bash
cd backend/django_app
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Run FastAPI in another terminal:

```bash
cd backend/fastapi_ai
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Run Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend URL:

- App: `http://localhost:3000`

## Notes

- Django is the JWT issuer and identity provider.
- FastAPI validates the same JWT using `JWT_SHARED_SECRET`.
- Database migrations are managed from Django.
