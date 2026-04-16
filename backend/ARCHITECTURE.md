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

## Documents OCR pipeline (Care Circle)

- Django app `documents` owns `MedicalDocument` storage metadata, RBAC, and REST routes under `/api/v1/`.
- Upload flow: validate MIME/size → persist row → **Supabase Storage** when `SUPABASE_*` env vars are set, otherwise **Django `default_storage`** under `MEDIA_ROOT` → **local OCR** for raw text → optional **Groq** structured extraction → **rule pass** (`extraction_rules`) → **conservative merge** (`merge_validate`) → save `extracted_json` / `extracted_json_rules` / `raw_ocr_text`.
- **Doctor** access uses `clinical.CarePlan` (assigned patient). **Caregiver** access uses `documents.PatientCaregiverLink` (create links in Django admin). **Patient** is limited to their own `user.id`.

## Screening PyTorch pipeline

- Route layer: `fastapi_ai/screening/router.py`
  - Handles multipart upload + RBAC (`patient`, `doctor`).
- Service layer: `fastapi_ai/screening/services/tongue_pt_service.py`
  - Decodes image, applies training-aligned preprocessing, executes PyTorch inference, and maps predictions.
- Config layer: `fastapi_ai/screening/config.py`
  - Centralizes model paths, normalization constants, class labels, and threshold.
- Model assets:
  - Source checkpoint: `fastapi_ai/screening/models/tongue/resnet50_best.pt`
