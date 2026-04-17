# Glunova — deployment plan

Single reference for **architecture**, **configuration**, **scripts**, and **operations**.

---

## 1. Architecture overview

| Tier | What | Billing |
|------|------|---------|
| Always on | **Next.js** (static export) → **Azure Static Web Apps** | Free tier (typical) |
| Always on | **Supabase** — PostgreSQL (+ optional Storage for documents) | Free tier (typical) |
| On demand | **Azure VM** `Standard_B4ms` (16 GB RAM): **Docker Compose** → **Nginx** + **Django** + **FastAPI** | Pay while VM is **running**; **`./stop.sh`** runs `az vm deallocate` to stop **compute** charges |

### 1.1 Repo layout (relevant paths)

| Path | Role |
|------|------|
| `docker-compose.yml` | Services: `django_app`, `fastapi_ai`, `nginx` |
| `backend/django_app/Dockerfile` | Django image (`glunova-django_app` when built) |
| `backend/fastapi_ai/Dockerfile` | FastAPI image (`glunova-fastapi_ai` when built) |
| `deploy/nginx/default.conf` | Nginx routing (mounted read-only into the `nginx` container) |
| `deploy.sh` | Build / push to ACR / save tar / SWA export / env hints / optional ACA rollout |
| `start.sh`, `stop.sh` | Azure VM **start** / **deallocate** (read `vm.env`) |
| `vm.env.example` | Template for VM name + resource group (+ optional ACR for `push`) |
| `deploy.env.example` | Template for **optional** Azure Container Apps + ACR |
| `scripts/azure/provision.sh` | One-time ACA: RG, ACR, Log Analytics, Container Apps **environment** |
| `scripts/azure/create-container-apps.sh` | One-time ACA: two apps (after images exist in ACR) |
| `frontend/Dockerfile.swa` | Static Next export → `frontend/out` |
| `frontend/staticwebapp.config.json` | Headers for Static Web Apps |

### 1.2 Nginx routing (port 80)

Single public HTTP entry on the VM (until you add TLS):

| Path prefix | Backend |
|-------------|---------|
| `/api/`, `/admin/`, `/static/`, `/media/` | Django (`django_app:8000`) |
| Everything else (`/screening`, `/docs`, `/openapi.json`, `/health`, …) | FastAPI (`fastapi_ai:8001`) |

Compose still publishes **8000** (Django) and **8001** (FastAPI) on the host for **local debugging**. On the production VM NSG you can allow only **22** (SSH) and **80** (Nginx).

---

## 2. Prerequisites

- **Docker** + Compose v2 ([Docker Desktop](https://www.docker.com/products/docker-desktop/) or Linux Engine).
- **Azure CLI** (`az`) for `start.sh` / `stop.sh` and for `./deploy.sh push` / ACA commands: [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), then `az login`.
- **Node / npm** (or Docker-only): `./deploy.sh frontend-swa-build` uses a Docker Node image by default.
- **Bash** for shell scripts: Git Bash or WSL on Windows; Linux/macOS natively.

### 2.1 Azure CLI — `containerapp` extension (ACA path only)

If you use **Azure Container Apps** scripts or `./deploy.sh aca-rollout`:

```bash
az extension add --name containerapp --upgrade --allow-preview true
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
```

If install fails (Pip errors): upgrade Azure CLI to the latest MSI, retry, or create Container Apps in the **Azure Portal** instead of CLI.

---

## 3. Environment files

### 3.1 `backend/.env` (required for `docker compose`)

Create at **`backend/.env`** (not committed). Compose passes this file into **both** Django and FastAPI containers.

**Core**

| Variable | Used by | Notes |
|----------|---------|--------|
| `DATABASE_URL` | Django | Supabase Postgres URL; include `sslmode=require` |
| `DJANGO_SECRET_KEY` | Django | Strong random secret |
| `JWT_SHARED_SECRET` | Django + FastAPI | **Same value** in both; FastAPI reads `jwt_shared_secret` from this file via Pydantic |
| `DJANGO_DEBUG` | Django | `false` in production |
| `FRONTEND_ORIGINS` | Django CORS + CSRF trusted origins | Comma-separated origins, e.g. `https://<app>.azurestaticapps.net` |
| `FRONTEND_ORIGIN` | Django | Legacy single origin (optional if you use `FRONTEND_ORIGINS`) |

**Cookies (cross-origin: SWA + VM API on different sites)**

| Variable | Notes |
|----------|--------|
| `DJANGO_COOKIE_SECURE` | Usually inferred from `DEBUG=false` (secure cookies on HTTPS) |
| `DJANGO_COOKIE_SAMESITE` | Use **`None`** when the browser UI and Django API are **different sites** and you use HTTPS + secure cookies; default **`Lax`** is typical for local dev |

**Django / integrations** (set as needed)

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_STORAGE_BUCKET` | Documents / storage |
| `GROQ_API_KEY`, `GROQ_MODEL`, `OCR_LANGUAGE`, `LLM_*`, `RXNORM_*`, `MEDICATION_VERIFY_*` | OCR / LLM / medication verification |

**FastAPI — tongue model** (at least one strategy)

| Variable | Purpose |
|----------|---------|
| `TONGUE_PT_MODEL_PATH` | Absolute path to `resnet50_best.pt` inside the container (bind mount, baked image, or after download) |
| `TONGUE_PT_MODEL_URL` | Optional HTTPS URL (e.g. Blob **SAS**). If set and the target file is missing/small, FastAPI **downloads** at startup (default save path `/tmp/glunova_models/resnet50_best.pt` unless `TONGUE_PT_MODEL_PATH` is set) |

FastAPI also uses `FRONTEND_ORIGINS` / `FRONTEND_ORIGIN` for CORS (same values as Django).

Full checklist on demand:

```bash
./deploy.sh print-env-hint
```

### 3.2 `vm.env` (for `./start.sh` / `./stop.sh`, optional ACR `push`)

Copy `vm.env.example` → **`vm.env`** (gitignored).

| Variable | Required for | Example |
|----------|----------------|----------|
| `AZURE_RESOURCE_GROUP` | start/stop | `glunova-rg` |
| `AZURE_VM_NAME` | start/stop | `glunova-b4ms` |
| `AZURE_ACR_NAME` | `./deploy.sh push` / `all` | Globally unique, alphanumeric, 5–50 chars |

### 3.3 `deploy.env` (optional — Azure Container Apps + ACR)

Copy `deploy.env.example` → **`deploy.env`** when using ACA. Used by `./deploy.sh push`, `./deploy.sh aca-rollout`, and `scripts/azure/*.sh`.

---

## 4. VM — first-time setup

1. Create a **Linux** VM (**Ubuntu 22.04 LTS** recommended), size **`Standard_B4ms`**, authentication (SSH key).
2. **NSG:** allow **22** (SSH), **80** (HTTP). Optionally **443** when you add TLS.
3. On the VM: install **Docker Engine** + **Compose plugin** — [Install on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
4. Clone this repository on the VM.
5. Create **`backend/.env`** (section 3.1).
6. From repo root on the VM:

   ```bash
   docker compose up -d
   ```

   Or: `make backend-rebuild` (builds and starts **Django + FastAPI + Nginx**).

7. **Django migrations** (once per new DB), inside the Django container:

   ```bash
   docker compose exec django_app python manage.py migrate
   ```

8. Health checks (from VM or your PC, using the VM public IP):

   - `http://<vm-ip>/api/` (Django routes under `/api/`)
   - `http://<vm-ip>/health` (FastAPI)
   - `http://<vm-ip>/docs` (FastAPI OpenAPI)

---

## 5. Images — build, push to ACR, or save tar

From the **repo root** (loads `vm.env` and/or `deploy.env` if present):

| Command | What it does |
|---------|----------------|
| `./deploy.sh build` | `docker compose build` (aliases: `docker-build`) |
| `./deploy.sh push` | Tags `glunova-django_app` / `glunova-fastapi_ai` as `…/glunova-django:<tag>` and `…/glunova-fastapi:<tag>`, pushes to `AZURE_ACR_NAME.azurecr.io` (alias: `acr-push`) |
| `./deploy.sh save` | Writes `dist/glunova-images-<tag>.tar` for `docker load -i …` on a VM without registry access |
| `./deploy.sh all` | `build` then `push` |
| `./deploy.sh print-env-hint` | Prints env variable reminders |

**`IMAGE_TAG`:** defaults to short `git` SHA or a timestamp; set `IMAGE_TAG` in the environment to override.

**Typical flows**

- **Build on the VM:** clone + `backend/.env` + `docker compose build && docker compose up -d` (no ACR required).
- **Build on laptop, push ACR, pull on VM:** run `./deploy.sh push` on laptop; on VM `az acr login -n <acr>` and either **re-tag/pull** with a custom Compose override (advanced) or **build on VM** anyway using the same Dockerfile contexts.
- **Air-gapped VM:** `./deploy.sh save`, copy `dist/*.tar` to the VM, `docker load -i …`, then `docker compose up -d` (Nginx image pulls from Docker Hub on first run).

---

## 6. Static frontend (Azure Static Web Apps)

1. Set public API base (through Nginx on the VM):

   ```bash
   export NEXT_PUBLIC_DJANGO_API_URL='http://<vm-public-ip>'
   export NEXT_PUBLIC_FASTAPI_API_URL='http://<vm-public-ip>'
   ```

   Use **HTTPS** + a real DNS name once Nginx terminates TLS; both variables should share the **same origin** if all traffic goes through Nginx.

2. Build static export:

   ```bash
   ./deploy.sh frontend-swa-build
   ```

   Output: **`frontend/out`** (+ ship `frontend/staticwebapp.config.json` with the app).

3. Deploy **`frontend/out`** to Static Web Apps (Azure Portal, GitHub Action, or [Static Web Apps CLI](https://learn.microsoft.com/azure/static-web-apps/get-started-cli)).

**Note:** Static export does **not** run a Node server; the UI still calls Django/FastAPI in the browser. HttpOnly cookies + `credentials: 'include'` require correct **`FRONTEND_ORIGINS`** and **`DJANGO_COOKIE_SAMESITE=None`** when UI and API are on **different** HTTPS sites.

---

## 7. VM lifecycle (from your workstation)

```bash
cp vm.env.example vm.env   # edit AZURE_RESOURCE_GROUP, AZURE_VM_NAME
./start.sh                 # az vm start
./stop.sh                  # az vm deallocate — stops compute billing
```

Requires `az login` and rights on the subscription.

---

## 8. Tongue PyTorch model (production)

The default path is under `backend/fastapi_ai/screening/models/` and is **gitignored**; images built from a clean clone do **not** contain `resnet50_best.pt` unless you add it.

| Approach | Summary |
|----------|---------|
| **Private build** | Place `resnet50_best.pt` in `screening/models/tongue/` on the build host **before** `docker compose build`; do not commit the file. |
| **`TONGUE_PT_MODEL_URL`** | HTTPS URL (e.g. time-limited Blob SAS); downloaded at FastAPI **process startup** if the file is not already present. |
| **`TONGUE_PT_MODEL_PATH`** | Point to an existing file (e.g. after download, or **Azure Files** mount mapped into the container). |
| **Azure Blob / Files** | Upload once; mount or download + set `TONGUE_PT_MODEL_PATH`. |

Without a valid checkpoint, tongue inference routes respond as **model missing**; other APIs can still run.

---

## 9. Optional — Azure Container Apps (legacy layout)

If you deploy backends to **Container Apps** instead of (or in addition to) the VM:

1. `cp deploy.env.example deploy.env` — set a **globally unique** `AZURE_ACR_NAME`.
2. `bash scripts/azure/provision.sh` — RG, ACR, Log Analytics, Container Apps **environment**.
3. `./deploy.sh build && ./deploy.sh push` — images in ACR.
4. `bash scripts/azure/create-container-apps.sh` — creates Django + FastAPI apps (first time).
5. Configure secrets/env in the Portal (same logical variables as section 3.1, per app).
6. Updates: `./deploy.sh push` then `./deploy.sh aca-rollout` (needs `deploy.env` + `containerapp` extension).

---

## 10. Redeployment (day 2)

**VM + Compose (current default):**

```bash
git pull
docker compose build --no-cache   # when Dockerfiles or deps change
docker compose up -d
```

Re-run migrations only when Django migrations change:

```bash
docker compose exec django_app python manage.py migrate
```

**Frontend:** re-export and redeploy `frontend/out` when UI or `NEXT_PUBLIC_*` values change.

**ACA:** `./deploy.sh push && ./deploy.sh aca-rollout` with matching `IMAGE_TAG` if you pin tags manually.

---

## 11. Troubleshooting

| Issue | Check |
|-------|--------|
| `docker compose` fails immediately | **`backend/.env` must exist** (Compose references `env_file`). |
| `az` not found (Windows) | Install Azure CLI; use a **new** PowerShell/cmd window; or add `az` to PATH. |
| ACR push: name rejected | `AZURE_ACR_NAME` must be **globally unique** across Azure. |
| SWA cannot log in / cookies missing | `FRONTEND_ORIGINS`, HTTPS, `DJANGO_COOKIE_SAMESITE=None`, `DJANGO_DEBUG=false`, CORS preflight. |
| Tongue inference 503 | Model file missing; set `TONGUE_PT_MODEL_URL` or `TONGUE_PT_MODEL_PATH` (section 8). |

For script usage:

```bash
./deploy.sh --help
```
