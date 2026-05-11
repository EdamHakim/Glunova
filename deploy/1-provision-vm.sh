#!/bin/bash
# Run this ONCE from your local machine (needs Azure CLI installed + logged in).
# az login   <-- run this first if not logged in

RESOURCE_GROUP="glunova-rg"
VM_NAME="glunova-vm"
LOCATION="francecentral"

# 1. Resource group
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION"

# 2. VM — B4ms: 4 vCPU, 16 GB RAM, ~$0.166/hour
az vm create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" \
  --image Ubuntu2204 \
  --size Standard_B4ms \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --output table

# 3. Open port 8000 (Django API)
az vm open-port \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" \
  --port 8000 \
  --priority 1001

# 4. Print the public IP
echo ""
echo "=== VM Ready ==="
az vm show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" \
  --show-details \
  --query publicIps \
  --output tsv
