## Architecture overview

- **Frontend:** Next.js (static export for Azure Static Web Apps)
- **Backend:** Django (API / business logic) and FastAPI (ML-heavy services), each in its own container
- **Database:** Supabase (PostgreSQL + optional storage) — no Azure-hosted database required

---

## Deployment plan

### 1. Containerization

- Docker images: `backend/django_app/Dockerfile`, `backend/fastapi_ai/Dockerfile`, and `docker-compose.yml` at repo root.
- Static frontend export: `frontend/Dockerfile.swa` (builds `frontend/out` for Static Web Apps).
- FastAPI image pulls CUDA-capable PyTorch (large). For smaller CPU-only images later, pin CPU wheels in `requirements.txt` or use a separate Dockerfile variant.

### 2. Container registry

- Push Django and FastAPI images to **Azure Container Registry (ACR)** using `./deploy.sh acr-push` (see below).

### 3. Backend deployment

- Run workloads on **Azure Container Apps** with separate apps for Django (port 8000) and FastAPI (port 8001).
- Configure **environment variables and secrets** in each app: `DATABASE_URL`, `DJANGO_SECRET_KEY`, `JWT_SHARED_SECRET`, `FRONTEND_ORIGINS`, `DJANGO_DEBUG=false`, Supabase keys, etc. Run `./deploy.sh print-env-hint` for a checklist.
- **Scaling:** raise FastAPI **CPU/memory and max replicas** in the Portal or `az containerapp update` if inference latency or queue depth requires it; Django can stay smaller.
- After first deploy, run **Django migrations** once (exec into the Django app or use a release job): `python manage.py migrate`.

### 4. Frontend deployment

- Build static assets: `./deploy.sh frontend-swa-build` (writes `frontend/out`). Set `NEXT_PUBLIC_DJANGO_API_URL`, `NEXT_PUBLIC_FASTAPI_API_URL`, and optionally `NEXT_PUBLIC_API_URL` to your **HTTPS** Container App URLs before building.
- Create an **Azure Static Web Apps** resource (free tier is fine), deploy the `frontend/out` folder and `frontend/staticwebapp.config.json` (Portal upload, GitHub Action, or [Azure Static Web Apps CLI](https://learn.microsoft.com/azure/static-web-apps/get-started-cli)).

### 5. Database connection

- Set `DATABASE_URL` on the Django (and FastAPI, if used) Container Apps to your Supabase connection string (`sslmode=require`). No Azure PostgreSQL required.

### 6. ML model storage

- Tongue checkpoint path: `backend/fastapi_ai/screening/models/` (gitignored). For production, either bake the `.pt` into a private image build, mount **Azure Files**, or download from **Azure Blob Storage** at container startup and point `TonguePtService` to that path (lazy load already supported).

---

## Prerequisites

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine).
2. [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli): `az login`, pick subscription, then:
   - `az extension add --name containerapp --upgrade`
3. Copy `deploy.env.example` to `deploy.env` and set globally unique `AZURE_ACR_NAME` (alphanumeric, 5–50 chars) and other names.

---

## First-time Azure setup (ordered)

```bash
./scripts/azure/provision.sh              # RG, ACR, Log Analytics, Container Apps env
./deploy.sh docker-build
./deploy.sh acr-push                      # needs deploy.env + az acr login
./scripts/azure/create-container-apps.sh  # creates both apps from images in ACR
```

Then in Azure Portal (or CLI), add **secrets/env** to both Container Apps, set **FRONTEND_ORIGINS** to your Static Web App URL, run migrations, and build the frontend with public API URLs before uploading `frontend/out`.

---

## Redeployment workflow

```bash
./deploy.sh all                 # docker-build + acr-push + rollout (uses deploy.env)
./deploy.sh frontend-swa-build # optional: refresh static site output
```

For backend-only iteration: `./deploy.sh rollout` after setting `IMAGE_TAG` to the tag you pushed.
