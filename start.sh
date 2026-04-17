#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ ! -f vm.env ]]; then
  echo "Missing vm.env — copy vm.env.example to vm.env and set AZURE_RESOURCE_GROUP and AZURE_VM_NAME." >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source vm.env
set +a
: "${AZURE_RESOURCE_GROUP:?}"
: "${AZURE_VM_NAME:?}"
command -v az >/dev/null 2>&1 || {
  echo "Azure CLI (az) not found." >&2
  exit 1
}
echo "Starting VM ${AZURE_VM_NAME} in ${AZURE_RESOURCE_GROUP}..."
az vm start --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_VM_NAME"
echo "Done. SSH in and run: cd <repo> && docker compose up -d"
