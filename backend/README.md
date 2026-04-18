# ⚙️ Glunova Backend (Hybrid)

[![Django](https://img.shields.io/badge/django_app-Django-092e20)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/fastapi_ai-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL-4169e1)](https://www.postgresql.org/)

Hybrid stack: **`django_app`** (identity, RBAC, relational data) and **`fastapi_ai`** (AI inference and multimodal routes) share one **PostgreSQL** database.

**Related:** [README](../README.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [features.md](../features.md)

---

## 🐳 Run with Docker

1. Set your database connection in **`backend/.env`** as `DATABASE_URL` (e.g. Supabase).
2. From the **repository root**:

```bash
docker compose up --build
```

---

## 🌐 Local service URLs

| Service | URL |
|---------|-----|
| Django API | http://localhost:8000 |
| FastAPI AI | http://localhost:8001 |
| FastAPI OpenAPI | http://localhost:8001/docs |

---

## 📚 Further reading

- [ARCHITECTURE.md](ARCHITECTURE.md) — JWT contract, OCR pipeline, screening layout
- [../README.md](../README.md) — full install, `make`, and `scripts/start_backends_local.bat`
