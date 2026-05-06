<p align="center">
  <img src="frontend/public/glunova_logo.png" alt="Glunova — AI-assisted diabetes care platform logo" width="280">
</p>
<p align="center">
  <a href="https://esprit.tn/"><img src="frontend/public/esprit_logo.png" alt="Esprit School of Engineering — se former autrement" width="220"></a>
</p>

<h1 align="center">Glunova</h1>

<p align="center">
  <strong>AI-assisted diabetes care platform</strong> — non-invasive screening, monitoring, nutrition, psychology, care coordination, medical document OCR, and clinical decision support.
</p>

<p align="center">
  <a href="https://esprit.tn/"><img src="https://img.shields.io/badge/Esprit_School_of_Engineering-3IA3-003366" alt="Esprit School of Engineering"></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Frontend-Next.js-000000" alt="Next.js"></a>
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-19-61dafb" alt="React"></a>
  <a href="https://www.typescriptlang.org/"><img src="https://img.shields.io/badge/TypeScript-3178c6" alt="TypeScript"></a>
  <a href="https://www.djangoproject.com/"><img src="https://img.shields.io/badge/API-Django-092e20" alt="Django"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/AI-FastAPI-009688" alt="FastAPI"></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/DB-PostgreSQL-4169e1" alt="PostgreSQL"></a>
</p>

---

## Overview

**Glunova** is a full-stack health technology project focused on **diabetes care**, **deep learning–assisted screening**, and **patient-centered digital health**. It combines a modern **React** and **Next.js** frontend with a **hybrid Python backend** (**Django** REST APIs and **FastAPI** for AI-heavy workloads), backed by **PostgreSQL**. The platform supports **API-driven** workflows, **medical document processing** and **OCR**, **nutrition automation** (including vision-based food analysis), and **role-based access control (RBAC)** for secure multi-user care scenarios.

This project was developed as part of coursework at **Esprit School of Engineering** (Class **3IA3**, **Innova Team**, **2026**). 
For a detailed feature matrix and team ownership, see [Features](https://citrine-gallon-8da.notion.site/58e0ec81b5c0828bb7950134d55c4566?v=d010ec81b5c08247a6430893c5067867).

---

## Features

- **Non-invasive screening** — multimodal signals (e.g. voice, tongue, eye) and fusion pipelines for risk insight without routine blood tests where the stack supports it.
- **Monitoring and alerts** — longitudinal history, risk tiers, health alerts, and progression-oriented views.
- **Nutrition and activity** — glycemic-index–aware weekly **wellness** planning (meals + exercise), exercise scheduling, and agentic nutrition guidance; ingredient and portion cues via **computer vision** (e.g. **YOLO-World** / **Ultralytics** in the nutrition pipeline).
- **Psychology and engagement** — multimodal emotional support, therapeutic modes, pediatric engagement, and accessible UX patterns.
- **Care circle and clinic** — family and caregiver coordination, **medical document OCR** and extraction orchestration, and clinical decision support surfaces.
- **Security and governance** — **JWT** authentication, **RBAC**, and shared relational data between services.

---

## Tech Stack

Icons are shown for quick scanning; dependency versions live in manifests under `frontend/` and `backend/`.

### Frontend

- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/nextdotjs.svg" width="18" height="18" alt=""> **Next.js** (App Router), <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/react.svg" width="18" height="18" alt=""> **React 19**, <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/typescript.svg" width="18" height="18" alt=""> **TypeScript**
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/tailwindcss.svg" width="18" height="18" alt=""> **Tailwind CSS** and <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/radixui.svg" width="18" height="18" alt=""> **Radix UI** primitives (see [frontend/package.json](frontend/package.json))
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/pnpm.svg" width="18" height="18" alt=""> **pnpm** for package management

### Backend

- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/django.svg" width="18" height="18" alt=""> **Django** — authentication, **RBAC**, migrations, REST APIs, document metadata and orchestration ([backend/django_app/](backend/django_app/))
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/fastapi.svg" width="18" height="18" alt=""> **FastAPI** — OCR and extraction, screening inference, AI routes; **OpenAPI** documentation at `/docs` ([backend/fastapi_ai/](backend/fastapi_ai/))
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/postgresql.svg" width="18" height="18" alt=""> **PostgreSQL** — shared database for Django and FastAPI
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/pytorch.svg" width="18" height="18" alt=""> **PyTorch** and **Ultralytics YOLO-World** — model-backed screening and nutrition vision paths (see [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md))

### Other tools

- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/gnu.svg" width="18" height="18" alt=""> **GNU Make** and [Makefile](Makefile) for repeatable backend lifecycle commands
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/uv.svg" width="18" height="18" alt=""> **`uv`** (Python) for fast local dependency installs in the provided Windows script
- <img src="https://cdn.jsdelivr.net/npm/simple-icons@v13/icons/nodedotjs.svg" width="18" height="18" alt=""> **Node.js 22+** for the frontend toolchain

---

## Directory structure

| Path | Role |
|------|------|
| [frontend/](frontend/) | Next.js app, UI, client integration with Django and FastAPI |
| [backend/django_app/](backend/django_app/) | Auth, RBAC, REST, migrations |
| [backend/fastapi_ai/](backend/fastapi_ai/) | AI and OCR routes, FastAPI OpenAPI |
| [backend/.env.example](backend/.env.example) | Backend env template; copy to `backend/.env` |
| [scripts/start_backends_local.bat](scripts/start_backends_local.bat) | Local Django + FastAPI on Windows |

---

## Getting started

### Prerequisites

- **Python 3** with [`uv`](https://github.com/astral-sh/uv) (recommended by the local script) or an equivalent **pip** workflow
- **PostgreSQL** reachable via **`DATABASE_URL`**
- **Node.js 22+** and [pnpm](https://pnpm.io/) (`npm install -g pnpm`)
- **Docker** (optional) for Compose-based backends
- **GNU Make** (optional); on Windows you can use `choco install make` or run the underlying **batch** commands directly

### Environment variables

Copy [`backend/.env.example`](backend/.env.example) to `backend/.env`, then edit values for your machine (see the comments in the template). Required before local backend startup:

```bash
# macOS / Linux (repository root)
cp backend/.env.example backend/.env
```

```bat
REM Windows CMD (repository root)
copy backend\.env.example backend\.env
```

Variables are loaded by Django and FastAPI (see **`backend/django_app/core/settings.py`** and **`backend/fastapi_ai/core/config.py`**). At minimum set **`DATABASE_URL`**. Extended notes: [backend/README.md](backend/README.md).

Optional **frontend** overrides (defaults follow the current host on ports **8000** / **8001**; see [frontend/lib/auth.ts](frontend/lib/auth.ts)):

- `NEXT_PUBLIC_DJANGO_API_URL`
- `NEXT_PUBLIC_FASTAPI_API_URL`

### Backend setup

Both options below run [scripts/start_backends_local.bat](scripts/start_backends_local.bat): it creates **`.venv`** at the repo root if needed, installs dependencies with **`uv`**, runs Django migrations, then launches **Django** on port **8000** and **FastAPI** on **8001**. You need **`backend/.env`** in place first (see [Environment variables](#environment-variables)). **Windows-only** (`start` launches separate console windows per service).

**Option A — GNU Make** (repository root)

```bash
make backend-local
```

**Option B — Run the script directly** (no Make). From the repository root in **Command Prompt** or **PowerShell**:

```bat
scripts\start_backends_local.bat
```

From **Git Bash** on Windows you can invoke the same file:

```bash
scripts/start_backends_local.bat
```

### Frontend setup

```bash
cd frontend
pnpm install
pnpm dev
```

Start the **backend** services first so authentication and **API** calls work end-to-end.

### Service URLs

| Service | URL |
|---------|-----|
| Django API | http://localhost:8000 |
| FastAPI | http://localhost:8001 |
| FastAPI OpenAPI | http://localhost:8001/docs |

### Architecture (high level)

```mermaid
flowchart LR
  Browser[Browser]
  Next[Next.js_frontend]
  Django[Django_API]
  FastAPI[FastAPI_AI]
  DB[(PostgreSQL)]

  Browser --> Next
  Next --> Django
  Next --> FastAPI
  Django --> DB
  FastAPI --> DB
```

Django owns identity, **RBAC**, and relational data; FastAPI serves **AI**- and **OCR**-heavy paths. Both use the same **PostgreSQL** database. Extended design notes: [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md).

### Documentation

- [features.md](features.md) — objectives, platform axes, feature ownership
- [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md) — **JWT**, **RBAC**, documents **OCR** pipeline, screening models
- [backend/README.md](backend/README.md) — hybrid backend and Docker notes

---

## Acknowledgments

This project was completed under the supervision of **Mme Jihene Hlel**, **Mr Fedi Baccar**, and **Mme Widad Askri** at **Esprit School of Engineering**, as part of the **Innova Team** (Class **3IA3**, **2026**).

We thank **Esprit School of Engineering** for the academic framework and mentorship that made this **full-stack AI** and **digital health** initiative possible.

---

<p align="center">
  <sub>Glunova · Innova Team · Esprit School of Engineering · 3IA3 · 2026</sub>
</p>
