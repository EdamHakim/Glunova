# Glunova Backend (Hybrid)

This backend uses a hybrid architecture:

- `django_app`: identity provider, RBAC authority, and clinical business data.
- `fastapi_ai`: high-frequency AI inference and multimodal services.
- Shared PostgreSQL database.

## Run with Docker

Set your Supabase connection string in `backend/.env` as `DATABASE_URL`.

From repository root:

```bash
docker compose up --build
```

## Local services

- Django API: `http://localhost:8000`
- FastAPI AI API: `http://localhost:8001`
- FastAPI docs: `http://localhost:8001/docs`
