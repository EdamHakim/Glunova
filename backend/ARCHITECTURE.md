# Glunova Backend Architecture

## Service split

- `django_app` is the source of truth for identity, RBAC roles, relational entities, and migrations.
- `fastapi_ai` is optimized for AI execution paths and real-time endpoints.
- Both services use the same PostgreSQL instance.

## Auth contract

- Django issues JWT access tokens via `api/auth/token/`.
- Tokens carry role claims (`patient`, `doctor`, `caregiver`).
- FastAPI validates JWT signatures with the shared secret and enforces endpoint-level RBAC.

## Clean architecture guidance

- Keep transport layer in `router.py` files.
- Add business orchestration in explicit service modules per domain.
- Keep model adapters and persistence concerns isolated from inference logic.
