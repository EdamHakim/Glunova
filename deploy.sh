#!/usr/bin/env bash
# Glunova: build Docker images, push to ACR, roll out Azure Container Apps.
# Prerequisites: Docker, Azure CLI (`az`), `az login`, extensions:
#   az extension add --name containerapp --upgrade
#
# Setup: copy deploy.env.example -> deploy.env and set names for your subscription.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -f deploy.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source deploy.env
  set +a
fi

require_az() {
  command -v az >/dev/null 2>&1 || {
    echo "Azure CLI (az) not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli" >&2
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

docker_build() {
  require_docker
  docker compose build
}

acr_push() {
  require_docker
  require_az
  : "${AZURE_ACR_NAME:?Set AZURE_ACR_NAME in deploy.env}"
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
  echo "Set IMAGE_TAG=$tag for rollout (or export IMAGE_TAG before rollout)."
  export IMAGE_TAG="$tag"
}

rollout() {
  require_az
  : "${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP in deploy.env}"
  : "${AZURE_CONTAINERAPP_DJANGO:?Set AZURE_CONTAINERAPP_DJANGO in deploy.env}"
  : "${AZURE_CONTAINERAPP_FASTAPI:?Set AZURE_CONTAINERAPP_FASTAPI in deploy.env}"
  : "${AZURE_ACR_NAME:?Set AZURE_ACR_NAME in deploy.env}"
  local tag
  tag="$(image_tag)"
  local acr_server="${AZURE_ACR_NAME}.azurecr.io"
  local django_repo="${acr_server}/glunova-django:${tag}"
  local fastapi_repo="${acr_server}/glunova-fastapi:${tag}"

  az containerapp update \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_CONTAINERAPP_DJANGO" \
    --image "$django_repo"
  az containerapp update \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_CONTAINERAPP_FASTAPI" \
    --image "$fastapi_repo"

  echo "Container Apps updated to tag ${tag}."
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
  echo "Wrote $ROOT/frontend/out — deploy this folder to Azure Static Web Apps."
}

print_env_hint() {
  cat <<'EOF'
Set these on each Container App (secrets via --secrets, then reference in --env-vars):

Django (glunova-django):
  DATABASE_URL            Supabase Postgres (sslmode=require)
  DJANGO_SECRET_KEY
  JWT_SHARED_SECRET       Must match FastAPI jwt_shared_secret
  DJANGO_DEBUG=false
  FRONTEND_ORIGINS        https://your-swa.azurestaticapps.net (comma-separated if several)
  DJANGO_COOKIE_SAMESITE  None  (required when UI and API are on different sites; needs HTTPS / secure cookies)
  SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_STORAGE_BUCKET (if used)
  GROQ_API_KEY, etc.

FastAPI (glunova-fastapi):
  JWT_SHARED_SECRET       Same as Django
  DATABASE_URL            If SQLAlchemy features need it
  FRONTEND_ORIGINS        Same as Django

After first deploy, run Django migrations once, for example:
  az containerapp exec -g <rg> -n <django-app> --command "python manage.py migrate"
(or use a one-off Job / release pipeline)

PyTorch checkpoint (tongue model) is gitignored. Copy resnet50_best.pt into the image build
context or mount from Azure Files / download from Blob at startup (see deployment_plan.md).
EOF
}

usage() {
  cat <<'EOF'
Usage: ./deploy.sh <command>

  docker-build       Build Django + FastAPI images (docker compose build)
  acr-push           Tag glunova-* images and push to AZURE_ACR_NAME
  rollout            Update both Container Apps to IMAGE_TAG (or current git SHA)
  all                docker-build, then acr-push, then rollout
  frontend-swa-build Static Next export via Node container (writes frontend/out)
  print-env-hint     List recommended Container Apps environment variables

One-time Azure resources: run scripts/azure/provision.sh after configuring deploy.env
EOF
}

cmd="${1:-}"
case "$cmd" in
  docker-build) docker_build ;;
  acr-push) acr_push ;;
  rollout) rollout ;;
  all)
    docker_build
    acr_push
    rollout
    ;;
  frontend-swa-build) frontend_swa_build ;;
  print-env-hint) print_env_hint ;;
  ""|-h|--help|help) usage ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
