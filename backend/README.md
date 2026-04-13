# Glunova API (FastAPI)

Production-oriented backend for the **Glunova** medical AI platform: diabetes monitoring, care coordination, JWT auth, RBAC, and monitoring entities aligned with `functionnalities_context.md`.

## Stack

- FastAPI, Pydantic v2, Uvicorn  
- PostgreSQL (tested with Supabase-compatible URLs)  
- SQLAlchemy 2.x + Alembic  
- JWT access + refresh (refresh rows stored hashed in DB)  
- `bcrypt` password hashing  
- SlowAPI rate limits (stricter on auth routes)  
- Pytest (unit tests; no DB required for default suite)

## Quick start (local)

1. **Python 3.12+** recommended (3.13 works with current dependencies).

2. Create a virtualenv, install deps, configure env:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env: DATABASE_URL, SECRET_KEY (≥32 chars)
   ```

3. **Migrations** (PostgreSQL must be reachable):

   ```bash
   export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/glunova"
   python -m alembic upgrade head
   ```

4. **Run the server**:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Open interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Docker Compose (API + Postgres)

From the **repository root**:

```bash
export GLUNOVA_SECRET_KEY="$(openssl rand -hex 32)"
docker compose up --build
```

Apply migrations inside the API container (one-off):

```bash
docker compose exec api python -m alembic upgrade head
```

API: [http://127.0.0.1:8000](http://127.0.0.1:8000) · Health: `GET /health`

## API layout (`/api/v1`)

| Area | Endpoints (summary) |
|------|---------------------|
| **Auth** | `POST /auth/register/{patient,doctor,caregiver}`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| **Users** | `GET/PATCH /users/me` |
| **Patients** | `GET/PATCH /patients/me`, `GET /patients` (doctor/caregiver), `GET/PATCH /patients/{id}` |
| **Doctors** | `GET/PATCH /doctors/me`, assign/unassign patients, list assigned patients |
| **Caregivers** | `GET/PATCH /caregivers/me`, link/unlink patients |
| **Appointments** | CRUD-style create/list/get/patch/delete with RBAC |
| **Medical** | `GET /medical/patients/{id}/clinical-summary` (patient + assigned doctor) |
| **Monitoring** | Screenings, alerts, care plans under `/monitoring/...` |

Send `Authorization: Bearer <access_token>` for protected routes.

## RBAC (high level)

- **Patient**: own profile, appointments, screenings/alerts/care plans where self; cannot create clinical alerts or arbitrary care plans for others.  
- **Doctor**: assigned patients only for clinical/monitoring writes; can update assigned patient profiles.  
- **Caregiver**: linked patients — list/read limited patient summary, read linked appointments and monitoring lists; cannot delete appointments or resolve alerts.

## Security & compliance notes

This codebase applies **defense-in-depth patterns** inspired by HIPAA/GDPR (TLS in production, strong secrets, RBAC, security headers, structured errors, refresh token revocation). It is **not** a certified compliance guarantee: you remain responsible for BAA with vendors, encryption, audit policies, and data retention.

## Tests

```bash
cd backend
python -m pytest
```

## Project structure

See repository `app/` tree: `core/`, `models/`, `schemas/`, `api/`, `services/`, `repositories/`, `db/`, `utils/`, `tests/`.
