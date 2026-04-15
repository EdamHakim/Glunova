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

Local startup scripts automatically load variables from `backend/.env`.

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

`make backend-up` runs in foreground and streams logs directly.

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
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Tongue PyTorch Inference

Artifacts:

- Input checkpoint: `backend/fastapi_ai/screening/models/tongue/resnet50_best.pt`

Run multipart inference request:

```bash
curl -X POST "http://localhost:8001/screening/tongue/infer" \
  -H "Authorization: Bearer <jwt_token>" \
  -F "patient_id=1" \
  -F "image=@/absolute/path/to/tongue.jpg"
```

Model readiness endpoint:

- `GET http://localhost:8001/screening/tongue/health`

## Run Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend URL:
- App: `http://localhost:3000`

## Notes
- Session persistence is handled by rolling `refresh_token` cookies.
- Cross-origin credentials (CORS) are enabled for `localhost:3000` to `localhost:8000/8001`.
- Database migrations must be run in Django to enable the token blacklist: `python manage.py migrate`.
