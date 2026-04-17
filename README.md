# Glunova

AI-powered healthcare platform focused on diabetes monitoring, prevention, and care coordination.

## Architecture

- `frontend/`: Next.js user interface.
- `backend/django_app`: core API for authentication, RBAC, and clinical data management.
- `backend/fastapi_ai`: AI engine for screening, psychology, nutrition, clinic, and kids services.
- Shared PostgreSQL on Supabase via `DATABASE_URL`.

## Prerequisites

- Python 3.11+
- uv (for Python dependency management)
- Node.js 20+
- pnpm
- Docker Desktop (optional, for containerized backend)
- GNU Make (optional, for shortcut commands)
- Tesseract OCR installed locally for Django OCR features
- Poppler installed locally if you want scanned PDF OCR fallback outside Docker

## Environment Setup

Create `backend/.env` (or copy from `backend/.env.example`) and set:

- `DATABASE_URL` (Supabase PostgreSQL URL with `sslmode=require`)
- `DJANGO_SECRET_KEY`
- `JWT_SHARED_SECRET`
- `DJANGO_DEBUG` (usually `true` for dev)

Local startup scripts automatically load variables from `backend/.env`.

OCR-related environment variables you can tune in `backend/.env`:

```bash
OCR_LANGUAGE=eng
TESSERACT_PSM=6
TESSERACT_OEM=3
OCR_PDF_TEXT_MIN_CHARS=80
OCR_PDF_MAX_PAGES=5
OCR_PDF_RASTER_DPI=200
OCR_IMAGE_MAX_DIM=2200
OCR_IMAGE_MIN_DIM=1200
OCR_IMAGE_CONTRAST=1.35
OCR_IMAGE_BINARIZE=true
OCR_IMAGE_THRESHOLD=170
POPPLER_PATH=
```

`OCR_LANGUAGE` supports multi-language packs such as `eng+fra` when those Tesseract language files are installed.

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

The Django Docker image now installs `tesseract-ocr`, `tesseract-ocr-eng`, and `poppler-utils`, which enables image OCR plus scanned-PDF raster fallback in containers.

Backend URLs:

- Django API: `http://localhost:8000`
- FastAPI API: `http://localhost:8001`
- FastAPI docs: `http://localhost:8001/docs`

## Run Backend (Local)

Install dependencies once:

```bash
uv pip install -r backend/requirements.txt
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

For local OCR support:

- Linux: install `tesseract-ocr`, desired language packs such as `tesseract-ocr-fra`, and `poppler-utils`.
- Windows: install Tesseract plus the needed `tessdata` language packs, install Poppler, and set `POPPLER_PATH` if `pdftoppm` is not on `PATH`.
- If Poppler is missing, scanned PDFs gracefully fall back to the existing text-only PDF extraction path.

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
