#!/usr/bin/env bash
# Create Django + FastAPI Container Apps (run after images exist in ACR).
# Requires: deploy.env, ./scripts/azure/provision.sh already run, ./deploy.sh acr-push done.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -f deploy.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source deploy.env
  set +a
fi

: "${AZURE_RESOURCE_GROUP:?}"
: "${AZURE_ACR_NAME:?}"
: "${AZURE_CONTAINERAPPS_ENV:?}"
: "${AZURE_CONTAINERAPP_DJANGO:?}"
: "${AZURE_CONTAINERAPP_FASTAPI:?}"

command -v az >/dev/null 2>&1 || {
  echo "Azure CLI (az) required." >&2
  exit 1
}

ACR_USER="$AZURE_ACR_NAME"
ACR_PASS="$(az acr credential show --name "$AZURE_ACR_NAME" --query 'passwords[0].value' -o tsv)"
ACR_SERVER="${AZURE_ACR_NAME}.azurecr.io"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
DJANGO_IMAGE="${ACR_SERVER}/glunova-django:${TAG}"
FASTAPI_IMAGE="${ACR_SERVER}/glunova-fastapi:${TAG}"

echo "Creating ${AZURE_CONTAINERAPP_DJANGO} (${DJANGO_IMAGE})..."
az containerapp create \
  --name "$AZURE_CONTAINERAPP_DJANGO" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --environment "$AZURE_CONTAINERAPPS_ENV" \
  --image "$DJANGO_IMAGE" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --output none

echo "Creating ${AZURE_CONTAINERAPP_FASTAPI} (${FASTAPI_IMAGE})..."
az containerapp create \
  --name "$AZURE_CONTAINERAPP_FASTAPI" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --environment "$AZURE_CONTAINERAPPS_ENV" \
  --image "$FASTAPI_IMAGE" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8001 \
  --ingress external \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 0 \
  --max-replicas 5 \
  --output none

echo "Done. URLs:"
az containerapp show -g "$AZURE_RESOURCE_GROUP" -n "$AZURE_CONTAINERAPP_DJANGO" --query properties.configuration.ingress.fqdn -o tsv | sed 's/^/  Django:  https:\/\//'
az containerapp show -g "$AZURE_RESOURCE_GROUP" -n "$AZURE_CONTAINERAPP_FASTAPI" --query properties.configuration.ingress.fqdn -o tsv | sed 's/^/  FastAPI: https:\/\//'
echo "Configure env vars (./deploy.sh print-env-hint), then open Static Web Apps for the frontend."
