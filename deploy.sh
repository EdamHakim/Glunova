#!/usr/bin/env bash
# Glunova VM stack: build Docker images, optional push to ACR, optional Static Web export.
# Optional: load vm.env and/or deploy.env (see vm.env.example, deploy.env.example).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for envf in vm.env deploy.env; do
  if [[ -f "$envf" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$envf"
    set +a
  fi
done

require_az() {
  command -v az >/dev/null 2>&1 || {
    echo "Azure CLI (az) not found." >&2
    exit 1
  }
}

require_docker() {
  command -v docker >/dev/null 2>&1 || {
    echo "Docker not found." >&2
    exit 1
  }
}

image_tag() {
  if [[ -n "${IMAGE_TAG:-}" ]]; then
    echo "$IMAGE_TAG"
    return
  fi
  if git rev-parse --short HEAD >/dev/null 2>&1; then
    git rev-parse --short HEAD
    return
  fi
  date +%Y%m%d%H%M%S
}

build() {
  require_docker
  docker compose build
}

push() {
  require_docker
  require_az
  : "${AZURE_ACR_NAME:?Set AZURE_ACR_NAME in vm.env or deploy.env}"
  local tag
  tag="$(image_tag)"
  local acr_server="${AZURE_ACR_NAME}.azurecr.io"
  local django_repo="${acr_server}/glunova-django:${tag}"
  local fastapi_repo="${acr_server}/glunova-fastapi:${tag}"

  az acr login --name "$AZURE_ACR_NAME"

  docker tag glunova-django_app:latest "$django_repo"
  docker tag glunova-fastapi_ai:latest "$fastapi_repo"
  docker push "$django_repo"
  docker push "$fastapi_repo"

  echo "Pushed:"
  echo "  $django_repo"
  echo "  $fastapi_repo"
  export IMAGE_TAG="$tag"
  echo "IMAGE_TAG=$tag (export before docker pull on the VM if you use pinned tags)."
}

save() {
  require_docker
  local out="${ROOT}/dist/glunova-images-$(image_tag).tar"
  mkdir -p "$ROOT/dist"
  docker save \
    glunova-django_app:latest \
    glunova-fastapi_ai:latest \
    -o "$out"
  echo "Wrote $out — copy to the VM and run: docker load -i $(basename "$out")"
  echo "(nginx uses public nginx:1.27-alpine; the VM pulls it on first compose up.)"
}

frontend_swa_build() {
  require_docker
  echo "Building static export via frontend/Dockerfile.swa -> frontend/out ..."
  docker build \
    -f "$ROOT/frontend/Dockerfile.swa" \
    --build-arg "NEXT_PUBLIC_DJANGO_API_URL=${NEXT_PUBLIC_DJANGO_API_URL:-}" \
    --build-arg "NEXT_PUBLIC_FASTAPI_API_URL=${NEXT_PUBLIC_FASTAPI_API_URL:-}" \
    --build-arg "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-}" \
    -t glunova-frontend-swa:build \
    "$ROOT/frontend"
  cid="$(docker create glunova-frontend-swa:build)"
  rm -rf "$ROOT/frontend/out"
  mkdir -p "$ROOT/frontend/out"
  docker cp "${cid}:/app/out/." "$ROOT/frontend/out/"
  docker rm "$cid" >/dev/null
  echo "Wrote $ROOT/frontend/out — deploy to Azure Static Web Apps."
}

print_env_hint() {
  cat <<'EOF'
VM / Docker Compose (backend/.env on the host, passed into containers):

  DATABASE_URL              Supabase Postgres (sslmode=require)
  DJANGO_SECRET_KEY
  JWT_SHARED_SECRET         Same value on Django and FastAPI (core/settings)
  FRONTEND_ORIGINS          https://<your-static-web-app>.azurestaticapps.net
  DJANGO_DEBUG=false        production
  DJANGO_COOKIE_SAMESITE    None if UI and API are different sites (HTTPS + secure cookies)

FastAPI tongue model (pick one):

  TONGUE_PT_MODEL_PATH      Absolute path to resnet50_best.pt (bind mount or baked image)
  TONGUE_PT_MODEL_URL       Optional HTTPS URL (e.g. Blob SAS); downloaded at startup if path missing

Static Web App build: set NEXT_PUBLIC_DJANGO_API_URL and NEXT_PUBLIC_FASTAPI_API_URL to the same
public origin if you terminate everything behind Nginx on the VM (e.g. http://<vm-ip> for both).

Optional Azure Container Apps (legacy): ./deploy.sh push && ./deploy.sh aca-rollout (needs deploy.env + containerapp extension).
EOF
}

aca_rollout() {
  require_az
  : "${AZURE_RESOURCE_GROUP:?}"
  : "${AZURE_CONTAINERAPP_DJANGO:?}"
  : "${AZURE_CONTAINERAPP_FASTAPI:?}"
  : "${AZURE_ACR_NAME:?}"
  local tag
  tag="$(image_tag)"
  local acr_server="${AZURE_ACR_NAME}.azurecr.io"
  az containerapp update --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINERAPP_DJANGO" \
    --image "${acr_server}/glunova-django:${tag}"
  az containerapp update --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINERAPP_FASTAPI" \
    --image "${acr_server}/glunova-fastapi:${tag}"
  echo "Container Apps updated to ${tag}."
}

usage() {
  cat <<'EOF'
Usage: ./deploy.sh <command>

  build              docker compose build (Django, FastAPI, Nginx config mount)
  push               tag + push Django/FastAPI images to AZURE_ACR_NAME (needs az acr login)
  save               docker save both app images to dist/*.tar (for air-gapped VM load)
  all                build + push (no VM start)
  frontend-swa-build static Next export -> frontend/out
  print-env-hint     environment variable checklist

Optional Container Apps:
  aca-rollout        update two Container Apps to current IMAGE_TAG / git SHA (needs deploy.env)

VM lifecycle (Azure CLI): ./start.sh  ./stop.sh  (configure vm.env first)
EOF
}

cmd="${1:-}"
case "$cmd" in
  build) build ;;
  push) push ;;
  save) save ;;
  all)
    build
    push
    ;;
  frontend-swa-build) frontend_swa_build ;;
  print-env-hint) print_env_hint ;;
  aca-rollout) aca_rollout ;;
  docker-build) build ;; # alias
  acr-push) push ;;      # alias
  ""|-h|--help|help) usage ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
