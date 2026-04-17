## Architecture overview

| Tier | What | Billing |
|------|------|---------|
| Always on | **Next.js** static export → **Azure Static Web Apps** (free) | Free tier |
| Always on | **Supabase** (Postgres + optional storage) | Free tier |
| On demand | **Azure VM** `Standard_B4ms` (16 GB RAM): **Docker Compose** → **Nginx** + **Django** + **FastAPI** | VM only while started; use `./stop.sh` to **deallocate** and stop compute charges |

Nginx listens on **port 80** and routes:

- `/api/`, `/admin/`, `/static/`, `/media/` → Django (port 8000 in the network)
- Everything else (e.g. `/screening`, `/docs`, `/health`) → FastAPI (port 8001)

Django and FastAPI are still published on **8000** and **8001** for local debugging; on the VM you can restrict the NSG to **80** (and 22 for SSH) only.

---

## VM: first-time setup

1. Create a **Linux** VM (Ubuntu 22.04 LTS), size **Standard_B4ms**, open NSG ports **22** (SSH) and **80** (HTTP).
2. Install Docker Engine + Compose plugin on the VM ([Docker docs](https://docs.docker.com/engine/install/ubuntu/)).
3. Clone this repo on the VM, create **`backend/.env`** (see repo `README.md`).
4. **`./deploy.sh print-env-hint`** for required variables (DB, secrets, `FRONTEND_ORIGINS`, cookies, model URL/path).
5. From the repo root on the VM: `docker compose up -d` (or `make backend-rebuild`).

---

## Images: build, push, or save

```bash
./deploy.sh build          # docker compose build
./deploy.sh push           # tag + push to ACR (set AZURE_ACR_NAME in vm.env or deploy.env)
./deploy.sh save           # write dist/*.tar for docker load on an air-gapped VM
./deploy.sh all            # build + push
```

On the VM, if using ACR: `az acr login -n <name>` then `docker compose pull` (after you change compose to use registry images — optional advanced step) or build directly on the VM with `docker compose build`.

---

## Static frontend (SWA)

Point **`NEXT_PUBLIC_DJANGO_API_URL`** and **`NEXT_PUBLIC_FASTAPI_API_URL`** at the same public base if everything goes through Nginx, e.g. `http://<vm-public-ip>` (or HTTPS if you terminate TLS in front of Nginx later).

```bash
export NEXT_PUBLIC_DJANGO_API_URL='http://<vm-ip>'
export NEXT_PUBLIC_FASTAPI_API_URL='http://<vm-ip>'
./deploy.sh frontend-swa-build
```

Deploy **`frontend/out`** to Static Web Apps.

---

## VM lifecycle (your workstation)

```bash
cp vm.env.example vm.env   # set AZURE_RESOURCE_GROUP, AZURE_VM_NAME
./start.sh                 # az vm start
./stop.sh                  # az vm deallocate (recommended when idle)
```

Requires **Azure CLI** and `az login`.

---

## Tongue model (FastAPI)

- **`TONGUE_PT_MODEL_PATH`**: absolute path to `resnet50_best.pt` (file share, bind mount, or baked in a private image build).
- **`TONGUE_PT_MODEL_URL`**: HTTPS URL (e.g. time-limited Blob SAS). If set, the file is downloaded at process startup before routes load, then `TONGUE_PT_MODEL_PATH` is set to the saved path (default `/tmp/glunova_models/resnet50_best.pt`).

---

## Optional: Azure Container Apps

If you still use Container Apps from an earlier layout: `./scripts/azure/provision.sh`, `./scripts/azure/create-container-apps.sh`, then `./deploy.sh push` and `./deploy.sh aca-rollout` with **`deploy.env`** filled in.
