# Glunova

AI-powered healthcare platform for diabetes monitoring, prevention, and care coordination (**Innova Team • ESPRIT • 3IA3 • 2026**).

## Repository layout

| Path | Description |
|------|-------------|
| `frontend/` | Next.js dashboard and patient-facing UI |
| `backend/` | **FastAPI** service — PostgreSQL, JWT, RBAC, appointments, monitoring (`backend/README.md`) |
| `functionnalities_context.md` | Product / AI feature map for upcoming modules |
| `docker-compose.yml` | Optional local **Postgres + API** stack |

## Backend quick start

See [`backend/README.md`](backend/README.md) for environment variables, Alembic migrations, and API documentation (`/docs`).

Typical flow:

1. Configure `backend/.env` from `backend/.env.example` (Supabase `DATABASE_URL`, `SECRET_KEY`).
2. `cd backend && pip install -r requirements.txt && alembic upgrade head`
3. `uvicorn app.main:app --reload --port 8000`

## Frontend quick start

```bash
cd frontend
pnpm install
pnpm dev
```

## Compliance note

Production deployments require appropriate legal agreements (e.g. **BAA** with hosting/DB providers), encryption, access logging, and retention policies. The backend README summarizes security-oriented practices implemented in code; they do not replace formal compliance work.
