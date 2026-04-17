#!/usr/bin/env bash
# One-time Azure provisioning: resource group, ACR, Log Analytics, Container Apps Environment.
# Does not create Container Apps (images must exist in ACR first).
#
# From repo root:
#   ./scripts/azure/provision.sh
# Then:
#   ./deploy.sh docker-build && ./deploy.sh acr-push
#   ./scripts/azure/create-container-apps.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -f deploy.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source deploy.env
  set +a
fi

: "${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP in deploy.env}"
: "${AZURE_LOCATION:?Set AZURE_LOCATION in deploy.env}"
: "${AZURE_ACR_NAME:?Set AZURE_ACR_NAME in deploy.env}"
: "${AZURE_CONTAINERAPPS_ENV:?Set AZURE_CONTAINERAPPS_ENV in deploy.env}"

command -v az >/dev/null 2>&1 || {
  echo "Azure CLI (az) required." >&2
  exit 1
}

az extension add --name containerapp --upgrade 2>/dev/null || true
az provider register --namespace Microsoft.App --wait 2>/dev/null || true
az provider register --namespace Microsoft.OperationalInsights --wait 2>/dev/null || true

echo "Creating resource group ${AZURE_RESOURCE_GROUP}..."
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --output none

echo "Creating Azure Container Registry ${AZURE_ACR_NAME}..."
az acr create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

echo "Creating Log Analytics workspace..."
WORKSPACE_NAME="${AZURE_RESOURCE_GROUP}-logs"
az monitor log-analytics workspace create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --location "$AZURE_LOCATION" \
  --output none

LOG_ID="$(az monitor log-analytics workspace show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query customerId -o tsv)"
LOG_KEY="$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query primarySharedKey -o tsv)"

echo "Creating Container Apps environment ${AZURE_CONTAINERAPPS_ENV}..."
az containerapp env create \
  --name "$AZURE_CONTAINERAPPS_ENV" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --location "$AZURE_LOCATION" \
  --logs-workspace-id "$LOG_ID" \
  --logs-workspace-key "$LOG_KEY" \
  --output none

echo "Infrastructure ready."
echo "Next: ./deploy.sh docker-build && ./deploy.sh acr-push"
echo "Then: ./scripts/azure/create-container-apps.sh"
